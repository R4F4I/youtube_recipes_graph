# YouTube-to-Obsidian Culinary Knowledge Pipeline

An automated, asynchronous pipeline that turns culinary video inspiration (like YouTube Shorts) into structured, deeply interconnected recipes inside your local Obsidian Vault.

## 🔴 The Problem
i like watching YT shorts alot, and i come across many inspiring recipes, but a end up ignoring a lot of them why?
1. **Missing Data:** Creators rarely put the exact measurements, full ingredient list, or step-by-step instructions in the description box.
2. **High Friction:** Saving links to notes apps creates an unorganized graveyard of URLs that require re-watching the video every time you want to cook.
3. **Flat Databases:** Standard recipe apps are isolated files. They don't let you see structural connections (e.g., *"Show me every recipe that uses 'Havarti Cheese' and 'Onions' but not 'Beef'"*), or map variations across different culinary components.

## 🟢 The Solution
An asynchronous, privacy-first local Python worker pipeline that bridges your phone, a lightweight cloud holding pen, Hugging Face AI providers, and Obsidian. 

By capturing video links on your phone, a local script handles the heavy lifting of extracting spoken audio transcripts, converting them into clean text, structuring them using a dynamic LLM cluster, and creating localized Obsidian Markdown files with native relational links.

## ⚙️ How It Solves It

```
[Phone (Todoist Queue)] ➔ [Local Python Script] ➔ [YT Transcript API]
                                    │
    [Obsidian Vault (.md Graph)] 🪓─┴─➔ [Hugging Face LLM Pool (JSON Parsing)]
```

1. **Frictionless Ingestion (Todoist Queue):** When watching a YouTube Short on your mobile device, a two-tap custom share macro pushes the URL to a dedicated Todoist project called `"yt links"`. You don't need your PC running 24/7; Todoist acts as an always-awake cloud buffer.
2. **One-Time Batch Processing (SQLite Deduplication):** When you run the script on your PC, it pulls the tasks. A local SQLite ledger (`pantry.db`) logs every processed `video_id`. If a link is a duplicate, it is discarded and cleared from the cloud automatically, completely eliminating wasted computing overhead.
3. **No-Audio Transcript Extraction:** The script utilizes `youtube-transcript-api` to pull raw timing chunks and stiches them using an official `TextFormatter` layout, cleaning it into a seamless paragraph of free-flowing prose.
4. **Dynamic Provider-Failover LLM Extraction:** The cleaned transcript is passed to the **Hugging Face Serverless Inference API**. To prevent API request rejections, it loops through a dynamic cluster of advanced text-generation models (`Qwen-2.5`, `Llama-3.1`, `Mistral-7B`). The AI isolates clean ingredient entities, separates them into functional cooking components (e.g., *The Sauce*, *The Marinade*), extracts quantities, and generates step-by-step recipes.
5. **Obsidian Native Graph Injection:** The script converts the structured AI response into an Obsidian-ready markdown file. 
    * **Flat Properties YAML:** It refines the components and ingredient objects into clean, non-nested metadata lists to fit Obsidian's property system flawlessly.
    * **Automatic Wiki-Linking:** It auto-wraps ingredients inside `[[Wiki-links]]` across both the frontmatter and the recipe content. 

Once saved into your vault, Obsidian instantly parses the connections. You get high-fidelity cooking instructions inside the note, and a fully populated, interconnected visual knowledge graph across your whole kitchen inventory without ever writing an edge map by hand.

## disclaimer

the script is NOT a replacement for the YouTube video, just a pointer, its supposed to help you filter out videos to filter to what is in your pantry, so that you make what *you* like with the ingredients *you* have