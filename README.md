# Firefox Session Explorer 🦊🔍

*The Swiss Army Knife for Firefox Tab Hoarders*

## About me
I am not a professional developer. (Just look at the spaghetti code, and you’ll understand.)
It’s just a mix of nights spent searching (or rather, scraping) Stack Overflow, collecting information from various tutorials, and asking AI for help. 
I made the horrible mistake of not noting down where I got things from. So if you find code that looks suspiciously similar, please reach out to me at apps@rd-an.de (if possible, with a link to the source—the commit for that part should be earlier than mine). I never intended to steal code. "Ehre wem Ehre gebührt!

And yes, I tried to "clean up" my original code (not yet released), but now it looks even worse than before. In German, we call this "Verschlimmbessern"—making something worse by trying to improve it.
If you’re a professional developer: See this as a "Try not to laugh challenge". If it makes you cry: Reach out to me and share your thoughts on what I need to change

The comments are a mix of languages, so don’t be surprised if you see German text. (My commenting skills also need improvement—before Git, I used to add useless comments like "NEU!", "NEW!", and other pointless statements, hoping not to lose track. Spoiler: It didn’t help.)


## What is this magnificent beast?

This application was born from the frustration of having too many tabs open and not enough organization. 
At the beginning i had written 3 seperate Tools. One for saving groups in seperated .csv's, one that extracts data with xpath and one that creates custom Urls for JDownloader... 
Then i tought: Why not combine these in one Application?
It grew into a full-featured session management and web scraping tool because, well, feature creep is real.

(Besides: Call me Paranoid, but DTFFSM [Don't Trust FireFox Session Managment] is my new motto of life)

Ever wondered what happens to all those tabs you've been collecting like digital Pokemon cards? Meet **Firefox Session Explorer** - the application that turns your browser's session files into a beautiful, organized, and slightly judgmental display of your browsing habits.

This isn't just another tab manager. Oh no, this is a full-blown archaeological expedition into the depths of your Firefox session files (those mysterious `.jsonlz4` files that Firefox keeps locked away like state secrets).

## Features That Will Make You Go "Wow, I Didn't Know I Needed This!"

### 🗂️ **Tab Organization Wizardry**
- Import your Firefox session files and see all your tabs organized by groups (if you have any)
- Finally understand why you have 47 tabs open about "how to organize your life"
- Edit group names and colors because aesthetics matter, even in chaos
- View your tab history in a beautiful tree structure that's more organized than your actual life
- A List that makes your tab chaos look almost... professional?

### 🔍 **XPath Web Scraping Superpowers**
- Extract data from websites using XPath rules (because sometimes you need to scrape that recipe from a blog with 47 paragraphs about the author's childhood)
- Image extraction because sometimes you need that perfect meme for later

### 🔧 **Advanced Tab Manipulation**
- Edit tab titles and URLs directly (because sometimes the internet is wrong)
- Move tabs between groups like a digital Marie Kondo
- Duplicate detection (finally, a way to find all 47 copies of that same Wikipedia article)

### 📊 **Data Management That Actually Makes Sense**
- SQLite database to store all your extracted goodies
- Duplicate detection (finally, an answer to "didn't I already save this?")

### 🎨 **Beautiful Interface**
- Dark mode support
- Favicon display (those tiny icons that spark joy)
- Responsive layout that, hopefully, doesn't make your eyes bleed
- Status bar that actually tells you useful things (at least i hope so) - get rid of the annoying MessageBoxes

### 🛠️ **Power User Features**
- Regex support for the brave souls who speak in `/[a-zA-Z]+/g`
- Search tabs by title, URL, or Hash (because sometimes you remember the weirdest details - just kidding. The downloaded pictures named by the Hash, so you can find the tab to the beautiful picture you stole)
- Bookmark export (turn your session into actual bookmarks like a responsible adult or  when you want to pretend you'll organize them later)
- JSON export for the developers who think they'll actually use this data

- Group editor for when you need to rename "Random Stuff" to "Important Random Stuff"
- Session file replacement (for when you want to clean up your actual Firefox)
- Pending changes tracking (for the commitment-phobic)

### **Planned (Prototype are Ready)** 
- Filter by custom tags (for when you've tagged everything but still can't find anything)
- CSV export for people who love spreadsheets more than human interaction
- Tag system for organizing scraped content
- Delete tabs you'll never actually read but feel guilty about closing
- Smart domain handling - some websites need special treatment (never worry about choosing the right scrapping mechanism again)
- Batch XPath processing for when you want to scrape 500 tabs at once and question your sanity simultaneously

## Why Would Anyone Need This?

Great question! Here are some totally legitimate use cases:

1. **Research Projects**: You've got 200 tabs open for your thesis and need to actually organize them
2. **Tab Hoarders**: If you regularly have 200+ tabs open and Firefox crashes make you cry
3. **Shopping Research**: Organize all those product pages you're "definitely going to buy from"
4. **Digital Archaeologists**: Those who need to excavate their browsing history like it's the lost city of Atlantis
5. **Procrastination Management**: Turn your tab chaos into organized procrastination
6. **Data Journalism**: Extract information from multiple sources systematically

## Technical Wizardry Under the Hood

- **Python + PySide6**: Because we like our GUIs crispy and our code readable
- **LZ4 Decompression**: Unlocks Firefox's secret session format
- **SQLite**: For when you need a database but don't want the drama of PostgreSQL
- **Playwright + Requests**: The dynamic duo of web scraping
- **XPath**: The CSS selector's more powerful (and slightly intimidating) cousin
- **Multi-threading**: Because nobody has time to wait for things to load

## How to Use This Thing

1. **Launch the application** (the hard part is over)
2. **Import a session file** - either load a recent one or import from your Firefox profile
3. **Marvel at your tab collection** - organized in a beautiful view
4. **Set up XPath rules** - for extracting data from websites (optional but fun)
5. **Scrape away** - extract data, images, or just organize your digital life
6. **Export your findings** - share your organized chaos with the world


## Contributing

Found a bug? Have a feature request? Want to add support for your favorite website's weird HTML structure? Contributions are welcome! Just remember:

- Keep it clean
- Keep it documented
- Keep it humorous (optional but appreciated)

## License

This project is licensed under the "Do Whatever You Want But Don't Blame Me If It Breaks" license. (Actually, check the LICENSE file for the real legal stuff. (TLDR: MIT License))

## Final Words

Whether you're a researcher, a digital hoarder, or just someone who wants to understand what the heck is in those Firefox session files, this tool is for you.

Happy tab hunting! 🦊✨

---

*P.S. - If you find yourself using this to organize more than 500 tabs, maybe it's time to consider that you might have a problem. But hey, at least now it's an organized problem!*

*"In a world of infinite tabs, be the session manager you wish to see in the world."* - Probably Gandhi, if he had Firefox