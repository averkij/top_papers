# 🔥 HF Daily Reviews by @doomgrad

Welcome to the reviews repository for HF Daily Papers! This project gathers insights and reviews of machine learning and AI research papers, and presents them in a creative and informative manner via Claude, GPT-4o, FLUX and others.

<img src="img/gen_image.png" alt="Top Papers Logo" width="640px" />

👉 [HFday.ru](https://hfday.ru)

🔺 [@doomgrad](https://t.me/doomgrad)

## Features

- 📚 Classification by topics
- 📅 Sorting by publication date and HF addition date
- 🔄 Syncing every 2 hours
- 💻 Hosted on GitHub
- 🌏 English, Russian, and Chinese
- 📈 Top by week/month (in progress)

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

## License

This project is licensed under the MIT License. Feel free to use and modify it as needed.

---
Enjoy exploring the world of machine learning papers with our unique, creatively generated reviews! Stay tuned and keep learning! 💾🛠️🧠
