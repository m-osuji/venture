PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE AnswerOptionEnum (
    answer_option_name TEXT PRIMARY KEY
);
INSERT INTO "AnswerOptionEnum" VALUES('option_1');
INSERT INTO "AnswerOptionEnum" VALUES('option_2');
INSERT INTO "AnswerOptionEnum" VALUES('option_3');
INSERT INTO "AnswerOptionEnum" VALUES('option_4');
CREATE TABLE BonusTypeEnum (
    bonus_type_name TEXT PRIMARY KEY
);
INSERT INTO "BonusTypeEnum" VALUES('ip');
INSERT INTO "BonusTypeEnum" VALUES('research_cost');
INSERT INTO "BonusTypeEnum" VALUES('expansion_strength');
INSERT INTO "BonusTypeEnum" VALUES('defence');
INSERT INTO "BonusTypeEnum" VALUES('regulation_mitigation');
INSERT INTO "BonusTypeEnum" VALUES('growth_bonus');
INSERT INTO "BonusTypeEnum" VALUES('attack');
INSERT INTO "BonusTypeEnum" VALUES('risk_control');
INSERT INTO "BonusTypeEnum" VALUES('tiebreak');
CREATE TABLE BonusValueEnum (
    bonus_value_name TEXT PRIMARY KEY
);
INSERT INTO "BonusValueEnum" VALUES('plus_two');
INSERT INTO "BonusValueEnum" VALUES('plus_one');
INSERT INTO "BonusValueEnum" VALUES('minus_one');
INSERT INTO "BonusValueEnum" VALUES('ignore_one');
INSERT INTO "BonusValueEnum" VALUES('plus_2');
INSERT INTO "BonusValueEnum" VALUES('plus_1');
INSERT INTO "BonusValueEnum" VALUES('minus_1');
INSERT INTO "BonusValueEnum" VALUES('Remove Attack');
INSERT INTO "BonusValueEnum" VALUES('Win Ties');
CREATE TABLE DifficultyLevelEnum (
    difficulty_level_name TEXT PRIMARY KEY
);
INSERT INTO "DifficultyLevelEnum" VALUES('easy');
INSERT INTO "DifficultyLevelEnum" VALUES('medium');
INSERT INTO "DifficultyLevelEnum" VALUES('hard');
CREATE TABLE Market (
    market_id INTEGER PRIMARY KEY,
    market_name TEXT NOT NULL,
    size TEXT NOT NULL,
    regulation_level TEXT NOT NULL,
    growth_potential TEXT NOT NULL,
    security_risk TEXT NOT NULL,
    key_topic TEXT NOT NULL,

	-- linking enum tables
    FOREIGN KEY (size) REFERENCES TraitsEnum(scale_value),
    FOREIGN KEY (regulation_level) REFERENCES TraitsEnum(scale_value),
    FOREIGN KEY (growth_potential) REFERENCES TraitsEnum(scale_value),
    FOREIGN KEY (security_risk) REFERENCES TraitsEnum(scale_value),
    FOREIGN KEY (key_topic) REFERENCES TopicEnum(topic_name)
);
INSERT INTO "Market" VALUES(1,'Healthcare','Large','High','Medium','Low','Ethics');
INSERT INTO "Market" VALUES(2,'Healthcare','large','high','medium','low','AI');
INSERT INTO "Market" VALUES(3,'Finance','large','high','medium','high','Data Science');
INSERT INTO "Market" VALUES(4,'Energy','large','medium','high','high','AI');
INSERT INTO "Market" VALUES(5,'Food & Water','large','medium','high','medium','Ethics');
INSERT INTO "Market" VALUES(6,'Transport','large','medium','high','medium','AI');
INSERT INTO "Market" VALUES(7,'Real Estate','large','medium','medium','medium','AI in Law');
INSERT INTO "Market" VALUES(8,'Pharmaceutics','medium','high','high','medium','AI');
INSERT INTO "Market" VALUES(9,'Manufacturing','medium','low','high','medium','AI');
INSERT INTO "Market" VALUES(10,'Technology','medium','low','high','high','Cybersecurity');
INSERT INTO "Market" VALUES(11,'Science','medium','medium','high','low','Data Science');
INSERT INTO "Market" VALUES(12,'Civil Engineering','medium','medium','medium','low','AI');
INSERT INTO "Market" VALUES(13,'Automotive','medium','medium','medium','medium','AI');
INSERT INTO "Market" VALUES(14,'Agriculture','medium','low','high','low','Ethics');
INSERT INTO "Market" VALUES(15,'Education','small','medium','medium','low','Education');
INSERT INTO "Market" VALUES(16,'Retail','small','low','medium','medium','Data Science');
INSERT INTO "Market" VALUES(17,'Law','small','high','low','low','AI in Law');
INSERT INTO "Market" VALUES(18,'Mining','small','low','high','high','Cybersecurity');
INSERT INTO "Market" VALUES(19,'Fisheries','small','low','medium','medium','Ethics');
INSERT INTO "Market" VALUES(20,'Cybersecurity','small','low','medium','high','Cybersecurity');
INSERT INTO "Market" VALUES(21,'Aerospace','medium','high','medium','high','AI');
INSERT INTO "Market" VALUES(22,'Weapons','small','high','low','very high','Ethics');
CREATE TABLE MarketLink (
    parent_market INTEGER NOT NULL,
    sub_market INTEGER NOT NULL,
    PRIMARY KEY (parent_market, sub_market),
    FOREIGN KEY (parent_market) REFERENCES Market(market_id),
    FOREIGN KEY (sub_market) REFERENCES Market(market_id)
);
CREATE TABLE Question (
    question_id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    option_1 TEXT NOT NULL,
    option_2 TEXT NOT NULL,
    option_3 TEXT NOT NULL,
    option_4 TEXT NOT NULL,
    answer TEXT NOT NULL,
    difficulty_level TEXT NOT NULL,

	-- linking enum tables
    FOREIGN KEY (topic) REFERENCES TopicEnum(topic_name),
    FOREIGN KEY (answer) REFERENCES AnswerOptionEnum(answer_option_name),
    FOREIGN KEY (difficulty_level) REFERENCES DifficultyLevelEnum(difficulty_level_name)
);
INSERT INTO "Question" VALUES(1,'AI in Law','A community center hires Rachel to assist multiple families appeal denied government benefits. With no additional staff to manage the caseload, she uses AI to autofill forms, flag missing data, and automate the sorting of case files based on deadlines. How is AI helping Rachel in this case to assist the families?','It is helping her skip the need for client interviews and documentation.','It is helping her guarantee successful outcomes for all benefit appeals.','It is helping her to automatically approve denied benefit applications.','It is helping her reduce costs and make services more affordable.','option_4','medium');
INSERT INTO "Question" VALUES(2,'Education','Élodie is a middle school teacher preparing reading materials with help from a general-purpose AI tool. She avoids entering student names, grades, or personal details into the system and instead uses only general class information. Which best practice is Élodie following?','Verify accuracy','Be transparent','Use AI to support, not replace','Protect student privacy','option_4','easy');
INSERT INTO "Question" VALUES(3,'Ethics','A weekly summary notifies a married couple that their grocery spending has increased by 15% since they moved to a new city. Match this personal finance scenario to the applicable AI enhancement.','Customized investment advice','Proactive fraud detection','Conversational financial assistance','Smart spending insights','option_4','easy');
INSERT INTO "Question" VALUES(4,'Cybersecurity','After detecting large, consistent balances in a checking account, a banking app suggests opening a high-yield savings account that better fits the user’s situation. Match this personal finance scenario to the applicable AI enhancement.','Customized investment advice','Personalized product recommendations ','Conversational financial assistance','Smart spending insights','option_2','hard');
INSERT INTO "Question" VALUES(5,'Ethics','A user asks a financial advisory app, “Should I pay off my student loans or start investing?” The app provides guidance based on the user’s income and loan interest rates. Match this personal finance scenario to the applicable AI enhancement.','Customized investment advice','Proactive fraud detection','Conversational financial assistance','Smart spending insights','option_3','easy');
INSERT INTO "Question" VALUES(6,'Cybersecurity','A credit card holder receives an alert stating, “Your usual coffee purchase was declined after an ATM withdrawal occurred 200 miles away”. Match this personal finance scenario to the applicable AI enhancement.','Customized investment advice','Proactive fraud detection','Conversational financial assistance','Smart spending insights','option_2','easy');
INSERT INTO "Question" VALUES(7,'Ethics','An investment platform explains why a low-risk bond fund fits a long-term retirement timeline and conservative investment approach.','Customized investment advice','Proactive fraud detection','Conversational financial assistance','Smart spending insights','option_1','easy');
INSERT INTO "Question" VALUES(8,'Cybersecurity','An app reviews several months of spending and sends a message explaining why entertainment costs increased after a recent subscription change. Match the personalization scenario with the corresponding AI technology.','Machine learning + large language models ','Large language models','Machine learning ','Natural language processing','option_1','hard');
INSERT INTO "Question" VALUES(9,'Cybersecurity','An app explains, "You''ve spent more on dining out this month. Here are three ways to reduce those costs."  Match the personalization scenario with the corresponding AI technology.','Machine learning + large language models ','Large language models','Machine learning ','Natural language processing','option_2','easy');
INSERT INTO "Question" VALUES(10,'Education','Chen uses AI to help her evaluate student essays. The AI tool provides detailed comments on each essay based on her rubric, giving her more time to meet with students who need extra guidance.','Decision-making AI','Predictive AI','Generative AI','Computer vision','option_3','easy');
INSERT INTO "Question" VALUES(11,'Cybersecurity','An app answers the question, "Should I pay off debt or start investing?" by using income, loan rates, and savings goals. Match the personalization scenario with the corresponding AI technology.','Natural language processing ','Machine learning','Large language models','Natural language processing  + large language models','option_4','medium');
INSERT INTO "Question" VALUES(12,'Cybersecurity','Lakshmi starts a new job with a longer commute. Now, her banking app shows a weekly update highlighting her increased spending on transportation. It also suggests that Lakshmi adjust her monthly budget accordingly. Which AI personalization enhancement does this scenario illustrate?','Personalized product recommendations','Proactive fraud detection','Smart spending insights ','Conversational financial assistance ','option_3','medium');
INSERT INTO "Question" VALUES(13,'Education','Jordan is using an AI tool to help prepare a lesson on the solar system. In his prompt, he instructs the AI tool to draft the material from his point of view, as a middle school science teacher, so the content aligns with how he would present it in class. Which prompt pattern is Jordan using?','Alternative approaches pattern','Flipped interaction pattern','Persona pattern','Template pattern','option_3','hard');
INSERT INTO "Question" VALUES(14,'Education','Aarav is a vice-principal who uses an AI tool to generate a first draft of the monthly staff update. Before sending it out, he carefully reviews all AI-generated sections to ensure they align with school goals and do not contain errors. Which best practice is Aarav following?','Verify accuracy','Maintain human oversite','Protect student privacy','Use ai to support, not replace','option_2','medium');
INSERT INTO "Question" VALUES(15,'Education','Selena is using an AI tool to help create a new unit on ancient civilizations. She needs the AI tool to produce a lesson plan with a clear, consistent structure, so she provides a specific format in her prompt. The response should include objectives, materials, activities, and assessments, in that order, and include complete content for each section.','Cognitive verifier pattern','Persona pattern','Alternative approaches pattern','Template pattern','option_4','easy');
INSERT INTO "Question" VALUES(16,'Cybersecurity','An investment platform reviews a customer’s age, income, savings goals, and risk tolerance. Then, it presents a long-term portfolio strategy with a clear explanation of how this strategy aligns to those goals. Which AI personalization enhancement does this scenario illustrate?','Conversational financial assistance ','Smart spending insights ','Proactive fraud detection','Customized investment advice ','option_4','medium');
INSERT INTO "Question" VALUES(17,'AI in Law','Associates at a large law firm spend a considerable amount of their work hours on document review and fact-checking. With AI-enabled automation, the time spent on these tasks drop, freeing up almost 10 hours per week. What benefit does this provide?','Increases productivity.','Enhances accessibility.','Improves legal research.','Strengthens case outcomes.','option_1','easy');
INSERT INTO "Question" VALUES(18,'AI in Law','Saul is working on a contract dispute case between companies located in different states and countries, each governed by its own legal system. He uses AI to extract relevant laws and statutes from multiple data sources, gathering insights accurately and quickly. What benefit does this provide?','Increases productivity.','Enhances accessibility.','Improves legal research.','Strengthens case outcomes.','option_3','easy');
INSERT INTO "Question" VALUES(19,'AI in Law','A small business owner receives a cost estimate of £2,000 for a contract review from a traditional law firm. Michelle, an independent legal professional who uses AI, agrees to do it for £500. What benefit does this provide?','Increases productivity.','Enhances accessibility.','Improves legal research.','Strengthens case outcomes.','option_2','easy');
INSERT INTO "Question" VALUES(20,'AI in Law','Marcus is preparing his arguments for a case that has several complex legal angles. Using AI, he finds similar cases from the past to analyse his arguments and refine his legal strategy. What benefit does this provide?','Increases productivity.','Enhances accessibility.','Improves legal research.','Strengthens case outcomes.','option_4','easy');
INSERT INTO "Question" VALUES(21,'AI in Law','In a personal injury lawsuit, the legal team constructs a comprehensive timeline of events leading to the incident. THe team uses generative AI to sort digital records and extract pertinent details from medical reports and accident logs.','Gathering facts.','Conducting legal research.','Analysing facts.','Drafting legal documents.','option_1','medium');
INSERT INTO "Question" VALUES(22,'AI in Law','In a property dispute case, a team of lawyers use AI to review the terms and conditions in the sale deed alongside relevant case laws. They want to identify clauses that might not work in court and refine their negotiation approach.','Gathering facts.','Conducting legal research.','Analysing facts.','Drafting legal documents.','option_3','easy');
INSERT INTO "Question" VALUES(23,'AI in Law','A junior lawyer wants to find out if tenants can be evicted without notice in New Jersey. He uses AI to find out the rent control laws of the state and the court rulings in previous tenant eviction cases, with and without notices, based on localities.','Gathering facts.','Conducting legal research.','Analysing facts.','Drafting legal documents.','option_2','medium');
INSERT INTO "Question" VALUES(24,'AI in Law','A lawyer shares basic case information with AI, and it creates a petition using appropriate legal language and structure.','Gathering facts.','Conducting legal research.','Analysing facts.','Drafting legal documents.','option_4','easy');
INSERT INTO "Question" VALUES(25,'AI in Law','A law firm uses AI to draft contracts. One day, a client’s confidential details appear in a presentation slide prepared by the marketing team, who had unintended access to the law firm’s internal systems. How can the law firm avoid such unintended consequences in the future?','Review output for potential bias.','Verify accuracy and transparency.','Choose phased implementation.','Protect data privacy.','option_4','easy');
INSERT INTO "Question" VALUES(26,'AI in Law','A group of policyholders claim that their medical claims were unfairly denied. Before drafting a defense, the insurance company’s legal team uses AI to review past judgments and case laws involving similar disputes. Which use case does this scenario demonstrate?','Conducting legal research','Analyzing facts','Gathering facts','Drafting legal documents.','option_1','easy');
INSERT INTO "Question" VALUES(27,'AI in Law','A legal firm''s AI repeatedly recommends longer sentences for defendants from a certain locality. What is the correct mitigation strategy?','Protect data privacy.','Verify accuracy and transparency.','Review output for potential bias.','nan','option_3','easy');
INSERT INTO "Question" VALUES(28,'AI in Law','Natasha uses generative AI to draft a legal memo, which includes a court case that doesn''t exist. What is the correct mitigation strategy?','Protect data privacy.','Verify accuracy and transparency.','Review output for potential bias.','nan','option_2','easy');
INSERT INTO "Question" VALUES(29,'AI in Law','A law firm uses AI to process sensitive client records, but stores identifiable details such as full names, case numbers, and locations. What is the correct mitigation strategy?','Protect data privacy.','Verify accuracy and transparency.','Review output for potential bias.','nan','option_1','easy');
INSERT INTO "Question" VALUES(30,'AI in Law','During a busy week, a paralegal relies solely on AI to generate case summaries and submit them to a senior partner without review. Later, the partner finds inaccuracies in the summaries and discovers misrepresented key points. How can the paralegal ensure that AI-generated outputs are accurate?','Choose phased implementation.','Verify accuracy and transparency.','Protect data privacy.','Review output for potential bias.','option_2','easy');
INSERT INTO "Question" VALUES(31,'AI in Law','A law firm deploys AI to generate intial drafts of a high volume of routine contracts up for renewal, helping to prevent backlogs.','Drafting legal documents.','Analysing facts.','Conducting legal research.','Gathering facts.','option_1','medium');
INSERT INTO "Question" VALUES(32,'Ethics','A company launches an AI-powered resume screening tool to help with hiring. However, the tool consistently favors candidates from certain universities, despite efforts to provide balanced training data. What ethical concept is most relevant in addressing this issue?','Providing transparency','Managing bias','Protecting intellectual property','Safeguarding privacy','option_2','easy');
INSERT INTO "Question" VALUES(33,'Ethics','A company develops an AI-powered hiring platform and the tool is trained on diverse demographic data to minimize bias. The platform is also regularly tested to promote equitable treatment across all candidates. Which ethical pillar does this scenario best demonstrate?','transparency','Fairness','Accountability','nan','option_2','easy');
INSERT INTO "Question" VALUES(34,'Ethics','An AI-powered hiring tool is designed to screen job applicants based on previous successful hires. However, the AI tool favors candidates similar to past hires because it was trained on past hiring patterns that lacked diversity. What ethical risk does this scenario highlight?','Privacy violation','Lack of fairness','Limited data security','Misuse of personal data','option_2','easy');
INSERT INTO "Question" VALUES(35,'Ethics','A company is developing an AI chatbot to assist customers with financial inquiries. To improve accuracy, the chatbot is trained using actual customer conversations. However, during a live session, a user notices that the chatbot references specific details from another customer’s past inquiry, suggesting that the data was not properly anonymized or protected. What ethical risk arises from using real customer data as AI training inputs?','Dataset imbalance','Lack of fairness','Lack of transparency','Data privacy violation','option_4','medium');
INSERT INTO "Question" VALUES(36,'Ethics','A social media platform uses AI to moderate content but does not disclose how its algorithm filters posts. Users begin to question whether the platform is suppressing certain viewpoints unfairly. What ethical concept should the company prioritize to address this concern?','Providing transparency','Managing bias','Reducing inaccurate information','Preventing harmful content','option_1','medium');
INSERT INTO "Question" VALUES(37,'Ethics','Who should be invited to a Business Framing exercise?','The business representative provides the business strategy perspective to the discussion.','An architect to validate the structural integrity of your business','The data scientist to address data privacy concerns','nan','option_1','hard');
INSERT INTO "Question" VALUES(38,'Ethics','The most complex and time-consuming process in deep learning is the creation of neural architecture','TRUE','FALSE','nan','nan','option_2','medium');
INSERT INTO "Question" VALUES(39,'Cybersecurity','Admir types, “Should I increase my emergency fund or pay down my credit card first?” His app responds with guidance based on income, balances, and interest rates. Which AI technologies work together to deliver this experience? ','Natural language processing and large language models
','Natural language processing, machine learning, and large language models','Machine learning and large language models','nan','option_2','hard');
INSERT INTO "Question" VALUES(40,'Cybersecurity','A fintech app operates in multiple countries and must comply with different local rules for handling customer data and providing financial guidance. The app’s development team limits personalization features to meet these requirements. Which factor most directly guides this personalization choice? ','Available data quality ','Regulatory requirements','Business objectives ','Customer segment and needs ','option_2','medium');
INSERT INTO "Question" VALUES(41,'AI','A fintech app serves freelance workers whose income varies month to month. The team behind the app designs it to prioritize flexible budgeting tools and cash-flow alerts rather than long-term investment recommendations. Which factor most directly guides this personalization choice?','Available data quality ','Regulatory requirements','Business objectives ','Customer segment and needs ','option_4','easy');
INSERT INTO "Question" VALUES(42,'Education','A software development team at a tech company needs to generate efficient code for automating routine tasks. The team also wants to explain complex code to help new members onboard quickly. Which IBM Granite model is best suited for this task?','Granite Code','Granite Japanese','Granite Multilingual','Granite Instruct','option_1','medium');
INSERT INTO "Question" VALUES(43,'AI','An e-commerce company wants to provide personalized shopping experiences for its customers by offering product recommendations based on individual preferences and purchase history. Which use case for large language models applies to this scenario?','Text extraction and analysis','Personalization','Sentiment analysis','Virtual assistants','option_2','easy');
INSERT INTO "Question" VALUES(44,'AI','A global e-commerce company needs to analyze customer reviews to identify trends and provide summarized insights that improve their marketing strategies. Which IBM Granite model should the company use to complete this task?','Granite Code','Granite Multilingual','Granite Instruct','Granite Guardian','option_3','medium');
INSERT INTO "Question" VALUES(45,'Education','A team requests the LLM to summarize a customer service email but receives vague and unhelpful responses. Upon review, they find the prompt was simply: “Summarize this.” Which prompting technique should the team use to improve the quality of the response?','Define the task clearly','Use simple and direct language','Be specific','Include examples','option_3','easy');
INSERT INTO "Question" VALUES(46,'AI','A product team asks the LLM to classify customer reviews as positive or negative but finds that the model misclassifies certain reviews. They later realize their prompt provided no examples of positive or negative classifications. Which prompting technique would best resolve this issue?','Define the task clearly','Use simple and direct language','Be specific','Include examples','option_4','easy');
INSERT INTO "Question" VALUES(47,'AI','A streaming platform aims to enhance user experience by offering content suggestions tailored to individual tastes. The AI agent analyzes watch history, user preferences, and interaction patterns to refine its recommendations over time. Which use case of AI agents does this example illustrate?','Fraud detection','Process automation','Virtual assistance','Personalization','option_4','easy');
INSERT INTO "Question" VALUES(48,'Cybersecurity','An AI agent email filtering system receives incoming messages and examines the content, sender information, and message structure to determine if an email is spam or legitimate. Which step is the AI agent performing in this scenario?','Learn and improve','Plan and execute an action','Process input data','Interpret the environment','option_3','medium');
INSERT INTO "Question" VALUES(49,'Education','An education platform uses an AI agent to customize learning experiences for students based on their progress. It detects areas where a student struggles, adjusts explanations, and modifies lesson difficulty in response to performance. Which type of AI agent is used by this education platform?','Goal-based AI agent','Utility-based AI agent','Learning AI agent','Reactive AI system','option_3','medium');
INSERT INTO "Question" VALUES(50,'AI','A self-driving car continuously monitors road conditions and changing traffic patterns throughout the day. Over time, it becomes more efficient at anticipating congestion and adjusting routes to avoid delays. Which step in the AI agent workflow helps it improve performance over time?','Make decisions','Execute an action','Learn and Improve','Interpret the environment','option_3','easy');
INSERT INTO "Question" VALUES(51,'AI','An airline uses an AI system that dynamically adjusts ticket prices based on demand, seasonality, and seat availability. Prices fluctuate in real time to optimize both revenue and customer affordability. What type of AI agent is used in this scenario?','Goal-based AI agent','Learning AI agent','Rule-based AI system','Utility-based AI agent','option_4','medium');
INSERT INTO "Question" VALUES(52,'AI','A company is deploying an AI-powered supply chain management system and is considering two solutions: Solution 1: An AI system that monitors stock levels, predicts demand using historical data, and generates restocking recommendations for suppliers. Solution 2: An AI system that coordinates tasks in real time, tracks inventory across locations, negotiates supplier contracts, and dynamically adjusts restocking decisions based on fluctuating demand. Identify the type of AI system used in each solution?','Both solution 1 and solution 2 are single-agent systems.','Both solution 1 and solution 2 are multiagent systems.','Solution 1 is a multiagent system; solution 2 is a single-agent system.','Solution 1 is a single-agent system; solution 2 is a multiagent system.','option_4','medium');
INSERT INTO "Question" VALUES(53,'AI','In a stock trading platform, AI agents perform different roles. Some analyze market trends and share insights to optimize investments, whereas others compete to secure the best trading opportunities. What type of multiagent system does this scenario represent?','Hierarchical multiagent system','Mixture of Experts multiagent system','Mixed multiagent system','Competitive multiagent system','option_3','medium');
INSERT INTO "Question" VALUES(54,'AI','An e-commerce company faces overwhelming customer inquiries about orders, refunds, and products. To enhance efficiency, it implements a multiagent system that manages daily tasks such as processing requests, analyzing sentiment, and handling routine queries, reducing delays and boosting customer satisfaction. Which key benefit of multiagent systems does this best demonstrate?','Dynamic problem solving','Cross-domain integration','Enhanced decision making','Automation of repetitive tasks','option_4','easy');
INSERT INTO "Question" VALUES(55,'Cybersecurity','A cybersecurity firm relies on multiagent systems to protect its network from evolving threats. The AI agents work together to detect vulnerabilities, analyze potential risks, and deploy automated countermeasures in real time to prevent cyberattacks. Which benefit of multiagent systems does this scenario demonstrate?','Enhanced decision making','Dynamic problem solving','Automating repetitive tasks','Cross-domain integration','option_2','medium');
INSERT INTO "Question" VALUES(56,'AI','In an AI-powered social media platform, some agents oversee global content ranking, others prioritize regional news trends, and another set of agents personalize articles for individual users. Which type of multiagent system does this represent?','Competitive multiagent system','Mixture of experts multiagent systems','Mixed multiagent system','Hierarchical multiagent system','option_4','hard');
INSERT INTO "Question" VALUES(57,'Education','Kiara is using a generative AI tool to draft promotional copy for an upcoming product launch. She enters a prompt describing the product and the target audience. The tool produces a polished draft in seconds. Which step of the generative AI process is happening when the tool produces the draft based on her prompt?','AI analyzes this data, looking for patterns and relationships between different pieces of information.','AI is fed a large amount of data. This could be anything from images and sounds to text and numbers.','AI uses what it has learned to create something new.','nan','option_3','easy');
INSERT INTO "Question" VALUES(58,'Education','A social media team needs to write 100 product descriptions for a new online catalog within a short time. They want a tool that can quickly draft the descriptions so the team can focus more on campaign strategy. Which task is generative AI best suited for in this situation?','Generating innovative ideas for new products','Creating content drafts at scale','Personizing product descriptions for different types of customers','Solving complex logic problems','option_2','easy');
INSERT INTO "Question" VALUES(59,'Education','Freyja uses a generative AI tool to draft marketing content, prompting it to “Write a short description of ABC smartwatch.” She''s dissatisfied with the result because it lacks details relevant to the target audience. What is the best refinement technique Freyja can apply to the prompt to generate the output she wants?','Adding the role the AI should take and expertise that should be used','Adding a constraint limiting the length of the response','Adding background information to contextualize the request','Adding the format the output should take','option_1','medium');
INSERT INTO "Question" VALUES(60,'Education','Ekon needs a brief summary of the key points in a blog post he is writing. He prompts, “Summarize this blog post.” Although the output is brief, he wants it provided as a list of bullets. What is the best refinement technique Ekon can apply to the prompt to generate the output he wants?','Adding background information to contextualize the request','Adding a constraint limiting the length of the response','Adding the format the output should take','Adding the role the AI should take and expertise that should be used','option_3','easy');
INSERT INTO "Question" VALUES(61,'AI','A product development team is struggling to analyze thousands of customer feedback entries to identify recurring issues and feature requests, so they turn to generative AI to automatically summarize and categorize the data. What generative AI task is the team performing?','Personalization','Problem solving','Content creation','Idea generation','option_2','easy');
INSERT INTO "Question" VALUES(62,'AI','Rina types into an LLM, “Explain how solar panels work in three simple sentences.” The system breaks her input into smaller parts, processes them, and then begins producing the response one word at a time until the response is complete. Which step of the LLM process is happening when the system produces the response word by word until the response is complete?','Contextual understanding','Prediction','Tokenization','Output generation','option_2','medium');
INSERT INTO "Question" VALUES(63,'Education','Cory is researching the benefits of electric cars for urban commuters and prompts, “Tell me about electric cars.” The AI-generated response is too broad. What is the best refinement technique Cory can apply to the prompt to generate the output he wants?','Adding the role the AI should take and expertise that should be used','Adding a constraint specifying the required content','Adding the format the output should take','Adding information describing exactly what you want the AI to do','option_4','medium');
INSERT INTO "Question" VALUES(64,'Education','A customer service team is introducing a new chatbot and want to give it a catchy name that users will remember. A developer on the team prompts the generative AI tool to provide a list of possible names. What generative AI task is the team performing?','Personalization','Problem solving','Content creation','Idea generation','option_4','easy');
INSERT INTO "Question" VALUES(65,'Education','A group of computer science students is training a generative AI tool to create new types of music. They have input thousands of existing songs across genres into the AI tool. Now, AI learns the rhythm, melody, and structure of the songs. Which step of the generative AI process does this describe?','AI analyzes this data, looking for patterns and relationships between the different pieces of information.','AI is fed a large amount of data. This could be anything from images and sounds to text and numbers.','AI uses what it has learned to create something new.','nan','option_1','easy');
INSERT INTO "Question" VALUES(66,'AI','Lorenzo asks an LLM to help him draft a professional email to his manager. He types, “Write a polite email requesting a one-on-one meeting with my manager next week.” The system analyzes his request, interprets the tone, and generates a clear, formal draft email. Which step of the LLM process is happening when the system determines Lorezo’s intent and tone?','Output generation','Contextual understanding','Tokenization','Prediction','option_2','medium');
CREATE TABLE Synergy (
    market1 INTEGER NOT NULL,
    market2 INTEGER NOT NULL,
    bonus_type TEXT NOT NULL,
    bonus_value TEXT NOT NULL,
    PRIMARY KEY (market1, market2),
    CHECK (market2 <> market1),
    FOREIGN KEY (market1) REFERENCES Market(market_id),
    FOREIGN KEY (market2) REFERENCES Market(market_id),
    FOREIGN KEY (bonus_type) REFERENCES BonusTypeEnum(bonus_type_name),
    FOREIGN KEY (bonus_value) REFERENCES BonusValueEnum(bonus_value_name)
);
INSERT INTO "Synergy" VALUES(13,4,'ip','plus_one');
INSERT INTO "Synergy" VALUES(18,4,'ip','plus_one');
INSERT INTO "Synergy" VALUES(17,8,'research_cost','minus_one');
INSERT INTO "Synergy" VALUES(3,8,'ip','plus_one');
INSERT INTO "Synergy" VALUES(5,15,'expansion_strength','plus_one');
INSERT INTO "Synergy" VALUES(11,6,'ip','plus_one');
INSERT INTO "Synergy" VALUES(11,5,'defence','plus_one');
INSERT INTO "Synergy" VALUES(3,5,'risk_control','ignore_one');
INSERT INTO "Synergy" VALUES(2,16,'defence','plus_one');
INSERT INTO "Synergy" VALUES(2,15,'ip','plus_one');
INSERT INTO "Synergy" VALUES(2,6,'research_cost','minus_one');
INSERT INTO "Synergy" VALUES(16,1,'regulation_mitigation','ignore_one');
INSERT INTO "Synergy" VALUES(9,10,'research_cost','minus_one');
INSERT INTO "Synergy" VALUES(9,19,'defence','plus_one');
INSERT INTO "Synergy" VALUES(9,8,'ip','plus_one');
INSERT INTO "Synergy" VALUES(10,7,'growth_bonus','plus_one');
INSERT INTO "Synergy" VALUES(21,20,'attack','plus_one');
INSERT INTO "Synergy" VALUES(21,3,'risk_control','Remove Attack');
INSERT INTO "Synergy" VALUES(20,9,'tiebreak','Win Ties');
INSERT INTO "Synergy" VALUES(19,2,'risk_control','ignore_one');
CREATE TABLE TopicEnum (
    topic_name TEXT PRIMARY KEY
);
INSERT INTO "TopicEnum" VALUES('AI');
INSERT INTO "TopicEnum" VALUES('Data Science');
INSERT INTO "TopicEnum" VALUES('Cybersecurity');
INSERT INTO "TopicEnum" VALUES('AI in Law');
INSERT INTO "TopicEnum" VALUES('Ethics');
INSERT INTO "TopicEnum" VALUES('Education');
CREATE TABLE TraitsEnum (
    scale_value TEXT PRIMARY KEY
);
INSERT INTO "TraitsEnum" VALUES('small');
INSERT INTO "TraitsEnum" VALUES('medium');
INSERT INTO "TraitsEnum" VALUES('large');
INSERT INTO "TraitsEnum" VALUES('very large');
INSERT INTO "TraitsEnum" VALUES('low');
INSERT INTO "TraitsEnum" VALUES('high');
INSERT INTO "TraitsEnum" VALUES('very high');
COMMIT;
