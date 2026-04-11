fetch("header.html")
  .then(res => res.text())
  .then(data => document.getElementById("header").innerHTML = data);

fetch("footer.html")
  .then(res => res.text())
  .then(data => document.getElementById("footer").innerHTML = data);

const routes = {
  "/": "home.html",
  "/tutorial": "pages/tutorial.html",
  "/game": "pages/game.html"
};


function loadRoute(path) {
  if (path === "/index.html") {
    path = "/";
  }

  const page = routes[path] || "home.html";

  fetch("/" + page)
    .then(res => {
      if (!res.ok) throw new Error("Page not found: " + page);
      return res.text();
    })
    .then(data => {
      document.getElementById("content").innerHTML = data;
    })
    .catch(err => {
      console.error(err);
      document.getElementById("content").innerHTML = "<h2>404 - Page not found</h2>";
    });
}

function navigate(path) {
  history.pushState({}, "", path);
  loadRoute(path);
}

window.onpopstate = () => {
  loadRoute(window.location.pathname);
};

loadRoute(window.location.pathname);

console.log("PATH:", window.location.pathname);