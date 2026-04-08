fetch("header.html")
  .then(res => res.text())
  .then(data => document.getElementById("header").innerHTML = data);

fetch("footer.html")
  .then(res => res.text())
  .then(data => document.getElementById("footer").innerHTML = data);

function loadPage(page) {
  fetch(page)
    .then(res => res.text())
    .then(data => {
      document.getElementById("content").innerHTML = data;
    });
}

loadPage("main_page.html");