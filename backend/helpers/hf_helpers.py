"""
Patches for HuggingFace Transformers/PEFT/Mellea compatibility (April 2026)
Importing this file automatically applies the necessary runtime patches

Tracking:
    github.com/huggingface/transformers + github.com/generative-computing/mellea
"""
import transformers.utils.peft_utils
import transformers.integrations.peft
import transformers.tokenization_utils_base
import transformers.generation.utils

def apply_patches():
    # bypass the HF PEFT version check for Granite 4.0
    transformers.utils.peft_utils.check_peft_version = lambda *args, **kwargs: None
    transformers.integrations.peft.check_peft_version = lambda *args, **kwargs: None

    # forward tensor attributes from dict to inner tensor as a catch-all for compatibility with Mellea's expected BatchEncoding
    original_getattr = transformers.tokenization_utils_base.BatchEncoding.__getattr__

    def safe_getattr(self, item):
        try:
            return original_getattr(self, item)
        except AttributeError:
            return getattr(self["input_ids"], item)

    transformers.tokenization_utils_base.BatchEncoding.__getattr__ = safe_getattr

    # unwrap the BatchEncoding dictionary into raw tensors no matter how Mellea passes them
    original_generate = transformers.generation.utils.GenerationMixin.generate

    def safe_generate(self, *args, **kwargs):
        new_args = list(args)
        
        # if Mellea passes the dictionary as the first positional argument
        if len(new_args) > 0 and hasattr(new_args[0], "keys") and "input_ids" in new_args[0]:
            # preserve the attention mask if it exists
            if "attention_mask" in new_args[0] and "attention_mask" not in kwargs:
                kwargs["attention_mask"] = new_args[0]["attention_mask"]
            # extract the raw tensor
            new_args[0] = new_args[0]["input_ids"]

        # if Mellea passes the dictionary as a keyword argument named 'inputs'
        if "inputs" in kwargs and hasattr(kwargs["inputs"], "keys") and "input_ids" in kwargs["inputs"]:
            if "attention_mask" in kwargs["inputs"] and "attention_mask" not in kwargs:
                kwargs["attention_mask"] = kwargs["inputs"]["attention_mask"]
            kwargs["inputs"] = kwargs["inputs"]["input_ids"]
            
        # if Mellea passes the dictionary as a keyword argument named 'input_ids'
        if "input_ids" in kwargs and hasattr(kwargs["input_ids"], "keys") and "input_ids" in kwargs["input_ids"]:
            if "attention_mask" in kwargs["input_ids"] and "attention_mask" not in kwargs:
                kwargs["attention_mask"] = kwargs["input_ids"]["attention_mask"]
            kwargs["input_ids"] = kwargs["input_ids"]["input_ids"]

        # pass the unwrapped tensors to Hugging Face
        return original_generate(self, *new_args, **kwargs)

    transformers.generation.utils.GenerationMixin.generate = safe_generate

# execute immediately when the file is imported
apply_patches()