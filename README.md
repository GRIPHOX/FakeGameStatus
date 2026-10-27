<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:5865F2,100:EB459E&height=220&section=header&text=Fake%20Game%20Status&fontSize=56&fontColor=ffffff&animation=fadeIn&fontAlignY=36&desc=Show%20any%20game%20on%20your%20Discord%20profile&descSize=18&descAlignY=58" width="100%" alt="Fake Game Status" />

<a href="#-quick-start">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=1200&color=5865F2&center=true&vCenter=true&width=640&lines=%F0%9F%8E%AE+Playing+any+game+in+one+click;%F0%9F%94%81+Auto-rotate+your+favourite+games;%F0%9F%8E%B2+Or+let+it+pick+random+games;%F0%9F%94%92+No+token.+No+self-bot.+Just+works." alt="Typing SVG" />
</a>

<br/>

<img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white" />
<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Discord-Activity-5865F2?style=for-the-badge&logo=discord&logoColor=white" />
<img src="https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge" />

<br/><br/>

<a href="../../releases/latest">
  <img src="https://img.shields.io/badge/%E2%AC%87%20Download-FakeGameStatus.exe-EB459E?style=for-the-badge&logoColor=white" height="42" alt="Download" />
</a>

</div>

---

## ✨ What is it?

**Fake Game Status** gives you a *"Playing …"* activity on Discord for **any game you choose**, without installing the game.

Discord shows a game when a process with that game's exe name is running **and has a window**. This app downloads Discord's own list of detectable games (10,000+), then starts a tiny window that uses the right exe name. Discord sees it and updates your status. 🎉

<div align="center">

| 🔍 Search | 🔁 Rotate | 🎲 Random | ✍️ Custom |
|:---:|:---:|:---:|:---:|
| Search 10k+ games from Discord's list | Cycle through your own list | Let the app pick games for you | Use any name you want |

</div>

## 🚀 Features

- 🔍 **Smart search**: ignores case, spaces and symbols, matches aliases and acronyms (`gta v`, `cs2`), maps `II` to `2`, and falls back to fuzzy matching (`minecrft` finds **Minecraft**)
- ▶️ **Play now** in one click, or double-click a result
- ⭐ **My games** list, saved between launches
- 🔁 **Auto change**: rotate your list or pick random games every *N* minutes, with an optional shuffle
- ⏱️ **Live status**: current game, elapsed time and a `next in mm:ss` countdown
- ✍️ **Custom name**: show any text as a game
- 🧹 **Clean exit**: Stop or closing the app kills the fake game, with nothing left running
- 🔒 **Safe**: no Discord token, no self-bot, and it never touches Discord's files

## 📥 Quick start

1. Download **`FakeGameStatus.exe`** from the [**latest release**](../../releases/latest).
2. Run it and wait a second for the game list to load.
3. Type a game name → **Search** → pick it → **Play now**.
4. Check your Discord profile. You're "playing" it! 🎮

> [!TIP]
> A small window with the game's name opens. You can **minimize** it, but don't close it. That window is what Discord detects.

<details>
<summary><b>🔁 Auto-rotating games</b></summary>
<br/>

1. Search for games and click **Add to my list** for each one.
2. Under **Auto change**, pick **Rotate my list** or **Random games**.
3. Set **Change every N minutes** (minimum 1) and tick **Shuffle** if you like.
4. Click **Start auto**.

</details>

<details>
<summary><b>✍️ Using a custom game name</b></summary>
<br/>

1. Click **Custom name...** and type any text.
2. The **first time only**, open Discord → **User Settings → Registered Games → "Add it!"**, pick the exe, and rename it to your text.
3. Discord remembers it from then on.

</details>

<details>
<summary><b>🛠️ Build from source</b></summary>
<br/>

Requires **Python 3.10+** on Windows.

```bash
py FakeGameStatus.pyw
```

To build the `.exe`, run **`build_exe.bat`**, or:

```bash
py -m pip install --upgrade pyinstaller
py -m PyInstaller --onefile --noconsole --clean --name FakeGameStatus FakeGameStatus.pyw
```

</details>

<details>
<summary><b>⚙️ How it works</b></summary>
<br/>

1. Downloads `https://discord.com/api/v9/applications/detectable` and caches it for one day in `%LOCALAPPDATA%\FakeGameStatus`.
2. Takes the game's Windows exe path (for example `win_x64/huntgame.exe`).
3. Copies itself to `%LOCALAPPDATA%\FakeGameStatus\bin\<that path>`.
4. Runs the copy in "child" mode, which opens a small window titled with the game's name.
5. The child closes itself if the main app dies, so nothing is left running.

</details>

## ⚠️ Notes

> [!WARNING]
> **Antivirus warnings:** apps packed with PyInstaller are often flagged by mistake, and this one also copies itself under other exe names. If Windows SmartScreen appears, click **More info → Run anyway**. You can always build the exe yourself from the source.

> [!CAUTION]
> This project is for fun and personal use. Using it to complete **Discord Quests** or to claim rewards may break Discord's Terms of Service. Use it at your own risk.

---

<div align="center">

Made with 💜 for the Discord community

⭐ **If you like it, star the repo!** ⭐

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:EB459E,100:5865F2&height=120&section=footer" width="100%" />

</div>
