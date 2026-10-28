const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync("index.html", "utf8");
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) {
  throw new Error("index.html must contain its inline script");
}
new vm.Script(match[1], { filename: "index.html" });
console.log("Embedded JavaScript syntax: ok");
