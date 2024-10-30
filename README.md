# 🔥 HF Daily Reviews by @doomgrad

Welcome to the automatically generated reviews repository for Hugging Face's daily papers! This project gathers insights and reviews of machine learning and AI research papers from Hugging Face, and presents them in a creative and informative manner.

👉 [HFday.ru](https://hfday.ru)

🔺 [@doomgrad](https://t.me/doomgrad)

## Project Overview

This project uses Python scripts to:

1. **Scrape Hugging Face Papers**: We extract papers published on Hugging Face, including titles, abstracts, and other key details.
2. **Generate Summaries via LLM API**: Abstracts are summarized using a large language model (Anthropic's Claude), generating brief, descriptive Russian summaries, tags, emojis, and catchy titles for each paper.
3. **Publish Reviews**: The summaries are transformed into a visually appealing HTML page and shared as a JSON feed. The HTML page is also available for easy browsing of the papers and their reviews.

The project automates the entire process, ensuring you get a curated overview of the latest Hugging Face papers every day.

## Features

- **Daily Reviews**: Automatically generated reviews of the most recent papers, including a short summary, tags, and related emoji.
- **Catchy Visuals**: Each paper comes with a catchy title and emoji that reflect the theme of the paper.
- **HTML Page with Dark and Light Themes**: Browse the latest reviews in an HTML page with an interactive light/dark theme toggle.
- **GitHub Actions Deployment**: The entire workflow is automated using GitHub Actions, ensuring the latest reviews are generated and deployed regularly.

## How It Works

- The script scrapes the **[Hugging Face Papers](https://huggingface.co/papers)** page daily.
- It extracts key information, such as title, abstract, and score of each paper.
- For each paper, the summary, tags, and other details are generated using **Anthropic's Claude** API.
- The generated information is saved in a JSON feed and presented on an HTML page.
- The deployment is automated using **GitHub Actions**, which runs every 2 hours to generate new reviews and deploy them to the website.

## GitHub Actions Deployment

The project is deployed automatically using GitHub Actions with the following workflow:

- **Workflow Name**: Issue Doomgrad Paper Review
- **Trigger**: The workflow runs every 2 hours (`cron: "0 */2 * * *"`) and can also be triggered manually.
- **Jobs**:
  - **Checkout Repository Content**: The repository content is checked out using `actions/checkout@v2`.
  - **Set Up Python**: Python 3.9 is set up using `actions/setup-python@v2`.
  - **Install Dependencies**: Required dependencies are installed using `pip install -r requirements.txt`.
  - **Run Python Script**: The `main.py` script is executed to generate the reviews.
  - **Commit Changes**: The changes are committed with a timestamped message.
  - **Push Changes**: The changes are pushed back to the GitHub repository.

This automation ensures that the reviews are always up-to-date and available for the audience without manual intervention.

The generated HTML page is deployed at [HFday.ru](https://hfday.ru), allowing users to browse the reviews easily.

## Usage

1. **Run the Python script** to generate the latest reviews:
   ```sh
   python generate_reviews.py
   ```
2. **HTML Page**: The reviews are saved in `index.html`, which can be opened in any browser for a beautiful reading experience.
3. **Log Files**: Logs are kept in `log.txt` and archived periodically for tracking purposes.

## Requirements

- Python 3.x
- **BeautifulSoup** for HTML parsing.
- **Anthropic API Key** to generate summaries.
- **Babel** for date formatting.

Install the required packages using:
```sh
pip install beautifulsoup4 babel anthropic tqdm
```

## Contributing

Feel free to contribute to this project! Pull requests are welcome for:
- Improving the HTML/CSS of the generated page.
- Enhancing the scraping or review generation logic.
- Improving the GitHub Actions workflow or adding new deployment features.

## License

This project is licensed under the MIT License. Feel free to use and modify it as needed.

---
Enjoy exploring the world of machine learning papers with our unique, creatively generated reviews! Stay tuned and keep learning! 💾🛠️🧠
