/*
@title: Cyber Vault: Quantum Heist
@author: Mohammed Touffeq
@tags: ['puzzle', 'action', 'cyberpunk']
@description: Infiltrate the high-security cyber vault! Collect the encryption cards, unlock the security firewalls, and extract the quantum core across 3 security sectors.
*/

const player = "p";
const wall = "w";
const key = "k";
const door = "d";
const core = "c";
const floor = ".";

setLegend(
  [player, bitmap`
................
....00000000....
...0888888880...
..083388883380..
..083388883380..
..088888888880..
..088888888880..
...0880000880...
....00111100....
...0199999910...
...0999999990...
...0999999990...
....09900990....
....09900990....
....000..000....
................
`],
  [wall, bitmap`
0000000000000000
0111111111111110
0199999999999910
0190000000000910
0190888888880910
0190800000080910
019080....080910
019080....080910
019080....080910
019080....080910
0190800000080910
0190888888880910
0190000000000910
0199999999999910
0111111111111110
0000000000000000
`],
  [key, bitmap`
................
................
.....55555......
....55...55.....
....55...55.....
.....55555......
......555.......
......555.......
......55555.....
......555.......
......55555.....
......555.......
......555.......
................
................
................
`],
  [door, bitmap`
0000000000000000
0444444444444440
0400000000000040
0405555555555040
0405.......55040
0405.......55040
0405...00..55040
0405..0550.55040
0405..0550.55040
0405...00..55040
0405.......55040
0405.......55040
0405555555555040
0400000000000040
0444444444444440
0000000000000000
`],
  [core, bitmap`
................
.......00.......
.....00DD00.....
....0DDDDDD0....
...0DD3333DD0...
..0DDD3553DDD0..
..0DDD3553DDD0..
.0DDDD3553DDDD0.
.0DDDD3553DDDD0.
..0DDD3553DDD0..
..0DDD3553DDD0..
...0DD3333DD0...
....0DDDDDD0....
.....00DD00.....
.......00.......
................
`]
);

setSolids([player, wall, door]);

const levels = [
  map`
wwwwwwwwwwwwwwww
w.............kw
w.wwwwww.wwwwwww
w.w....w.......w
w.w.ww.w.wwwww.w
w.w..w.w.....w.w
w.ww.w.wwwww.w.w
wp...w.....w...w
wwwwww.www.w.www
w......w...w...w
w.wwwwww.wwwww.w
w.w....w.....w.w
w.w.ww.wwwww.w.w
w...wd......cw.w
wwwwwwwwwwwwwwww
`,
  map`
wwwwwwwwwwwwwwww
wp...w.....w...w
w.ww.w.www.w.w.w
w.w..w...w...w.w
w.w.wwwwwwwwww.w
w.w..........w.w
w.wwwwwwwwww.w.w
w.w...k....w.w.w
w.w.wwwwww.w.w.w
w.w.w....w.w.w.w
w.w.w.ww.w.w.w.w
w...w..w...w...w
www.ww.wwwww.w.w
w...w..d....cw.w
wwwwwwwwwwwwwwww
`,
  map`
wwwwwwwwwwwwwwww
wp.....w.......w
wwwwww.w.wwwww.w
w....w.w.w...w.w
w.ww.w.w.w.w.w.w
w.wk...w.w.w.w.w
w.wwwwww.w.w.w.w
w........w.w.w.w
wwwwwwwwww.w.w.w
w..........w.w.w
w.wwwwwwwwww.w.w
w.w..........w.w
w.w.wwwwwwwwww.w
w...d.........cw
wwwwwwwwwwwwwwww
`
];

let currentLevel = 0;
let hasKey = false;

setMap(levels[currentLevel]);

const sndMove = tune`
  150: c4-10
`;

const sndKey = tune`
  200: e4-10 g4-10 c5-20
`;

const sndDoor = tune`
  200: f4-10 d4-10 a3-20
`;

const sndWin = tune`
  250: c4-10 e4-10 g4-10 c5-30 e5-20 g5-40
`;

function checkCollisions() {
  const p = getFirst(player);
  if (!p) return;

  // Check key pickup
  const keysOnTile = getTile(p.x, p.y).filter(s => s.type === key);
  if (keysOnTile.length > 0) {
    keysOnTile.forEach(k => k.remove());
    hasKey = true;
    playTune(sndKey);
  }

  // Check core reached
  const coresOnTile = getTile(p.x, p.y).filter(s => s.type === core);
  if (coresOnTile.length > 0) {
    playTune(sndWin);
    currentLevel++;
    if (currentLevel < levels.length) {
      hasKey = false;
      setMap(levels[currentLevel]);
    } else {
      clearText();
      addText("VAULT COMPLETED! YOU WIN!", { y: 7, color: "5" });
    }
  }
}

function tryOpenDoor(targetX, targetY) {
  const doors = getTile(targetX, targetY).filter(s => s.type === door);
  if (doors.length > 0 && hasKey) {
    doors.forEach(d => d.remove());
    hasKey = false;
    playTune(sndDoor);
    return true;
  }
  return false;
}

onInput("w", () => {
  const p = getFirst(player);
  if (!p) return;
  tryOpenDoor(p.x, p.y - 1);
  p.y -= 1;
  checkCollisions();
  playTune(sndMove);
});

onInput("s", () => {
  const p = getFirst(player);
  if (!p) return;
  tryOpenDoor(p.x, p.y + 1);
  p.y += 1;
  checkCollisions();
  playTune(sndMove);
});

onInput("a", () => {
  const p = getFirst(player);
  if (!p) return;
  tryOpenDoor(p.x - 1, p.y);
  p.x -= 1;
  checkCollisions();
  playTune(sndMove);
});

onInput("d", () => {
  const p = getFirst(player);
  if (!p) return;
  tryOpenDoor(p.x + 1, p.y);
  p.x += 1;
  checkCollisions();
  playTune(sndMove);
});
