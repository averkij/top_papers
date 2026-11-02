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

Claude and GPT requests, including structured output and embeddings, use [OpenRouter](https://openrouter.ai/docs/quickstart) through the OpenAI SDK. Set `OPENROUTER_API_KEY` in your local environment and add a repository Actions secret with the same name in GitHub. Both review workflows use this secret; `CLAUDE_KEY` and `OPENAI_KEY` are no longer required.

The daily reviews and topic classification use `anthropic/claude-haiku-5.5`; user-requested reviews use `anthropic/claude-sonnet-5.5` with low reasoning effort. GPT-4o mini workloads use `openai/gpt-6-luna`, and the GPT-4o fallback uses `openai/gpt-6.1-terra`, both with reasoning disabled. Embeddings use `openai/text-embedding-3-small` to preserve compatibility with existing vectors.

Run the manual **Check OpenRouter integration** workflow to verify all four chat models, structured output, and embeddings with small live requests. Locally, run `python -m scripts.check_openrouter` with `OPENROUTER_API_KEY` set.

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
