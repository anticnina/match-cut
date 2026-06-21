# MatchCut 

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-00e054?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/UI-PyQt6-14181c?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/Data-Pandas-ff8000?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas">
</p>

---

### ❓ What is this?

**MatchCut** is a desktop app that answers the question you've been too afraid to ask: *do you and your Letterboxd mutuals actually have compatible taste in film?* 

Enter your Letterboxd username. Pick a friend. Watch the truth unfold across **six cinematic slides** of data-driven judgment. 

ℹ️ *Named after the match cut - the film editing technique, a seamless cinematic transition based on similarity. Just like your perfect match!* ✂️

---

### ✨ Features

* 🔐 **Login with your Letterboxd username** — no password, no API key, no private inforamtion 
* 👤 **Live profile loading** — pulls your display name, avatar, and stats straight from Letterboxd.

<img width="2130" height="1582" alt="image" src="https://github.com/user-attachments/assets/66c36ee1-337b-48c3-acef-3c91373c8a24" />

* 👥 **Follower picker** — browse your following list and pick your first candidate

<img width="2130" height="1576" alt="image" src="https://github.com/user-attachments/assets/ac43c09a-be92-421c-b27d-4debf37a6fbb" />

* 🎞️ **Six-slide compatibility analysis:**
  * 🔄 **1. Co-watched count** — how many films you've both actually seen.
  * ✝️ **2. Mutual Favorites** — films you both gave high ratings or hearted. 
  * 💔 **3. Dealbreakers** — films where your ratings diverge by $1.5+$ or more stars. This is where friendships go to die.
  
  <img width="2134" height="1580" alt="image" src="https://github.com/user-attachments/assets/98a58dd5-e1f9-4218-831b-8eb4cba646e9" />

  * 🔮 **4. Genre Vibes** — your individual top genres (with percentages) and the one genre you're both secretly obsessed with.
  * 🍿 **5. Watch These Next** — films each of you loved that the other hasn't seen yet. The polite version of *"how have you not watched this?"*
  * 🏆 **6.Your MatchCut Score** — a final compatibility percentage, your names highlighted in Letterboxd orange and blue and one of three dynamic verdicts. No spoilers here — you'll have to run the analysis to see if you belong in a classic romance or if you're entering full cinematic enemy territory.

---

### ⚙️ How it works 

MatchCut scrapes Letterboxd directly — no official API needed, because Letterboxd doesn't have one and we're not here to let that stop us. 🛠️

* 📝 **Ratings** come from each user's public RSS feed (`/username/rss/`) — the one endpoint Cloudflare actually lets through without interrogating you.
* 🏷️ **Genres** are scraped from individual film pages using **JSON-LD** schema data embedded in the HTML. Eight concurrent workers do this in parallel so you don't age visibly while waiting. 🏎️
* 🖼️ **Poster images** are extracted from the RSS feed's `CDATA` description blocks. No TMDB key. No third-party API. Just regex and hope. 🙏
* 🧮 **Compatibility scoring** uses a proportional Jaccard-style algorithm for genres — meaning *"Horror at 47% each"* beats *"Drama at 3% each"* even if the ratio is the same. It's not just about equality, it's about passion. 🔥
* 💯 **The MatchCut Score** is calculated from shared favorites ($+5$ each, capped), genre overlap bonus, and a dealbreaker penalty. Starts at $50$ because you're already following each other, which counts for something.

---

### 🚀 Installation

```bash
# Clone the repository
git clone [https://github.com/anticnina/match-cut.git](https://github.com/anticnina/match-cut.git)
cd match-cut

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
