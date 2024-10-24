# %%
from glob import glob
from babel.dates import format_date
import helper
import constants as con

prev_papers = glob("./d/*.json")

len(prev_papers)


# %%
def make_html(data):
    data["papers"] = [x for x in data["papers"] if "error" not in x["data"]]
    article_classes = ""
    for paper in data["papers"]:
        if paper["score"] >= 20:
            article_classes += f'body.light-theme>div>main>article.x{paper["hash"]} {{ background: url("https://hfday.ru/img/{paper["pub_date"].replace("-","")}/{paper["hash"]}.jpg") !important; background-size: cover !important; background-position: center !important; background-blend-mode: lighten !important; background-color: rgba(255,255,255,0.91) !important;}}\n'

            article_classes += f'body.light-theme>div>main>article.x{paper["hash"]}:hover {{ background-color: rgba(255,255,255,0.95) !important;}}\n'

            article_classes += f'body.dark-theme>div>main>article.x{paper["hash"]} {{ background: url("https://hfday.ru/img/{paper["pub_date"].replace("-","")}/{paper["hash"]}.jpg") !important; background-size: cover !important; background-position: center !important; background-blend-mode: hue !important; background-color: rgba(60,60,60,0.9) !important; }}\n'

            article_classes += f'body.dark-theme>div>main>article.x{paper["hash"]}:hover {{ background-color: rgba(60,60,60,0.92) !important;}}\n'

    html = """
<!DOCTYPE html>
<html>
<head>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-C1CRWDNJ1J"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'G-C1CRWDNJ1J');
    </script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">"""

    html += f"<title>HF ({helper.format_subtitle(len(data['papers']))})</title>"

    html += (
        """
    <link rel="icon" href="favicon.svg" sizes="any" type="image/svg+xml">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@100..900&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #0989eacf;
            --secondary-color: #fff;
            --background-color: #f5f5f5;
            --text-color: #333333;
            --header-color: #0989eacf;
            --body-color: #f5f5f5;
            --menu-color: #002370;
        }
        body {
            font-family: 'Roboto Slab', sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        .a-clean {
            color: var(--secondary-color);
            text-decoration: none;
        }
        header {
            padding: 3em 0;
            text-align: center;
        }
        h1 {
            font-size: 2.4em;
            margin: 0;
            font-weight: 700;
        }
        h2 {
            # color: var(--primary-color);
            font-size: 1.2em;
            margin-top: 0;
            margin-bottom: 0.5em;
        }
        header p {
            font-size: 1.2em;
            margin-top: 0.5em;
            font-weight: 300;
        }
        main {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2em;
            padding: 10px 0 20px 0;
        }
        body.dark-tmeme>header {
            background-color: background-color: #333333;
            color: white;
        }
        body.dark-theme>div>main>article>div.article-content>p.meta {
            color: #fff;
        }
        body.light-theme>div>main>article>div.article-content>p.meta {
            color: #555;
        }
        body.dark-theme>div>main>article>div.article-content>p.pub-date {
            color: #ccc;
        }
        body.light-theme>div>main>article>div.article-content>p.pub-date {
            color: #555;
        }
        body.dark-theme>div>main>article>div.article-content>p.tags {
            color: #ccc;
        }
        body.light-theme>div>main>article>div.article-content>p.tags {
            color: #555;
        }
        body.light-theme>header {
            background-color: var(--header-color);
            color: white;
        }
        article {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23);
            transition: background-color 0.2s ease;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        .article-content {
            padding: 1.5em;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            position: relative;
            z-index: 1;
            cursor: pointer;
        }
        body.dark-theme>div>main>article {
            background-color: #444;
        }
        body.light-theme>div>main>article {
            background-color: #fff;
        }
        body.dark-theme>div>main>article:hover {
            background-color: #414141;
        }
        body.light-theme>div>main>article:hover {
            background-color: #fafafa;
        }
        .meta {
            font-size: 0.9em;
            margin-bottom: 0em;
        }
        .pub-date {
            font-size: 0.9em;
            margin-bottom: 0.8em;
            font-weight: 300;
        }
        .tags {
            font-size: 0.9em;
            margin-bottom: 1em;
            position: absolute;
            bottom: 10px;
            font-weight: 300;
            font-family: 'Roboto Slab';
        }
        .background-digit {
            position: absolute;
            bottom: -20px;
            right: -10px;
            font-size: 12em;
            font-weight: bold;
            color: rgba(0, 0, 0, 0.03);
            z-index: 0;
            line-height: 1;
        }
        .abstract {
            position: relative;
            max-height: 170px;
            overflow: hidden;
            transition: max-height 0.3s ease;
            cursor: pointer;
        }
        .abstract.expanded {
            max-height: 1000px;
        }
        .abstract-toggle {
            position: absolute;
            bottom: 4px;
            right: 0;
            cursor: pointer;
            color: var(--primary-color);
            float: right;
            font-weight: 400;
        }
        .explanation {
            background-color: #e8f5e9;
            border-left: 4px solid var(--secondary-color);
            padding: 1em;
            margin-top: 1.5em;
        }
        .links {
            margin-top: 1.5em;
            margin-bottom: 80px;
        }
        a {
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
            transition: color 0.3s ease;
        }
        a:hover {
            color: var(--secondary-color);
        }
        footer {
            background-color: var(--primary-color);
            color: white;
            text-align: center;
            padding: 1em 0;
            margin-top: 2em;
        }
        .light-theme {
            background-color: var(--body-color);
            color: #333333;
        }
        .dark-theme {
            background-color: #333333;
            color: #ffffff;
        }
        .theme-switch {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 50px;
            height: 30px;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 30px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 24px;
            width: 24px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: var(--primary-color);
        }
        input:checked + .slider:before {
            transform: translateX(20px);
        }
        .switch-label {
            margin-right: 10px;
        }
        .update-info-container {
            margin-top: 15px;
            margin-bottom: 0px;
            text-align: left;
        }
        .sort-container {
            margin-top: 15px;
            margin-bottom: 0px;
            text-align: right;
        }
        .sub-header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        .update-info-container {
            flex: 1;
        }
        .sort-container {
            flex: 2;
        }
        .sort-dropdown {
            padding: 5px 10px;
            font-size: 16px;
            border-radius: 5px;
            border: 1px solid #ccc;
            background-color: white;
            color: var(--text-color);
            font-family: 'Roboto Slab', sans-serif;
        }
        .sort-label {
            margin-right: 10px;
            font-size: 1.0em !important;
        }        
        .dark-theme .sort-dropdown {
            background-color: #444;
            color: white;
            border-color: var(--text-color);
        }
        .title-sign {
            display: inline-block;
            transition: all 0.5s ease;            
        }
        .rotate {
            transform: rotate(45deg) translateY(-6px);
            transform-origin: center;
        }
        .title-text {
            display: inline;
            padding-left: 10px;
        }
        .category-filters {
            margin-top: 20px;
            margin-bottom: 20px;
            text-align: center;
        }
        .category-button {
            display: inline-block;
            margin: 5px;
            padding: 5px 10px;
            border-radius: 15px;
            background-color: #f0f0f0;
            color: #333;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        .category-button.active {
            background-color: var(--primary-color);
            color: white;
        }
        .dark-theme .category-button {
            background-color: #555;
            color: #fff;
        }
        .dark-theme .category-button.active {
            background-color: var(--primary-color);
        }
        .category-toggle {
            display: none;
            margin-bottom: 10px;
            margin-top: 15px;
            cursor: pointer;
        }
        .clear-categories {
            display: inline-block;
            margin: 5px;
            padding: 5px 10px;
            border-radius: 15px;
            background-color: #f0f0f0;
            color: #333;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        .clear-categories:hover {
            background-color: #bbb;
        }
        .svg-container {
            display: inline-block;
            position: relative;
            overflow: hidden;
        }
        .svg-container span {
            position: relative;
            z-index: 1;
        }
        .svg-container svg {
            position: absolute;
            bottom: 0;
            left: 0;
            z-index: 0;
        }

        .nav-menu {
            background-color: var(--menu-color);
            padding: 2px 0 2px 0;
            display: inline-block;
            position: relative;
            overflow: hidden;
            width: 100%;
        }        
        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: left;
            gap: 3em;
        }
        .nav-container span a {
            color: white;
        }        
        .nav-item {
            color: white;
            padding: 3px 0px;
            cursor: pointer;
            font-weight: 400;
        }        
        .nav-item:hover {
            background-color: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.3);
        }
        
        .dark-theme .nav-menu {
            background-color: #333;
        }
        .dark-theme .nav-item {
            color: white;
        }
        
        .dark-theme .nav-item:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }
        
        @media (max-width: 600px) {
            .nav-container {
                flex-direction: row;
                gap: 1.5em;
            }            
            .nav-item {
                padding: 3px 0px;
            }
        }
        """
        + article_classes
        + """
        @media (max-width: 768px) {
            .category-filters {
                display: none;
            }
            .category-toggle {
                display: inline-block;
                width: 100%;
                text-align: left;
            }
            .category-filters.expanded {
                display: block;
                margin-top: 10px;
            }
        }
        @media (max-width: 600px) {
            .sub-header-container {
                flex-direction: column;
                align-items: flex-start;
            }
            .update-info-container {
                text-align: left;
                width: 100%;
                margin-bottom: 0px;
            }
            .sort-container {
                margin-top: 0px;
                text-align: left;
                width: 100%;
            .sort-dropdown {
                float: right;
            }
            .sort-label {
                margin-top: 5px;
                float: left;
            }
        }
    </style>
    <script>
    function toggleAbstract(id) {
        var abstract = document.getElementById('abstract-' + id);
        var toggle = document.getElementById('toggle-' + id);
        if (abstract.classList.contains('expanded')) {
            abstract.classList.remove('expanded');
            toggle.textContent = '...';
        } else {
            abstract.classList.add('expanded');
            toggle.textContent = '';
        }
    }
    function getTimeDiffRu(dateString) {
        const timeUnits = {
            minute: ["минуту", "минуты", "минут"],
            hour: ["час", "часа", "часов"],
            day: ["день", "дня", "дней"]
        };

        function getRussianPlural(number, words) {
            if (number % 10 === 1 && number % 100 !== 11) {
                return words[0];
            } else if (number % 10 >= 2 && number % 10 <= 4 && (number % 100 < 10 || number % 100 >= 20)) {
                return words[1];
            } else {
                return words[2];
            }
        }

        const pastDate = new Date(dateString.replace(" ", "T") + ":00Z");
        const currentDate = new Date();
        const diffInSeconds = Math.floor((currentDate - pastDate) / 1000);

        const minutes = Math.floor(diffInSeconds / 60);
        const hours = Math.floor(diffInSeconds / 3600);
        const days = Math.floor(diffInSeconds / 86400);

        if (minutes == 0) {
            return 'только что';
        }
        else if (minutes < 60) {
            return `${minutes} ${getRussianPlural(minutes, timeUnits.minute)} назад`;
        } else if (hours < 24) {
            return `${hours} ${getRussianPlural(hours, timeUnits.hour)} назад`;
        } else {
            return `${days} ${getRussianPlural(days, timeUnits.day)} назад`;
        }
    }
    function isToday(dateString) {
        const inputDate = new Date(dateString);
        const today = new Date();
        return (
            inputDate.getFullYear() === today.getFullYear() &&
            inputDate.getMonth() === today.getMonth() &&
            inputDate.getDate() === today.getDate()
        );
    }
    function formatArticlesTitle(number) {
        const lastDigit = number % 10;
        const lastTwoDigits = number % 100;

        let word;

        if (lastTwoDigits >= 11 && lastTwoDigits <= 14) {
            word = "статей";
        } else if (lastDigit === 1) {
            word = "статья";
        } else if (lastDigit >= 2 && lastDigit <= 4) {
            word = "статьи";
        } else {
            word = "статей";
        }

        return `${number} ${word}`;
    }
    </script>
</head>"""
    )

    html += f"""
<body class="light-theme">
    <header>
        <div class="container">
            <a href="https://hfday.ru" class="a-clean"><h1 class="title-sign" id="doomgrad-icon">🔺</h1><h1 class="title-text" id="doomgrad">{con.TITLE_LIGHT}</h1></a>
            <p>{data['date']} | {helper.format_subtitle(len(data['papers']))}</p>
        </div>
        <div class="theme-switch">
            <label class="switch">
                <input type="checkbox" id="theme-toggle">
                <span class="slider"></span>
            </label>
        </div>
    </header>
    <div class="nav-menu">
        <div class="nav-container">
            <span class="nav-item" id="nav-prev"><a href="/d/{feed['link_prev']}">⬅️ {feed['short_date_prev']}</a></span>
            <span class="nav-item" id="nav-next"><a href="/d/{feed['link_next']}">➡️ {feed['short_date_next']}</a></span>
            <!--<span class="nav-item" id="nav-weekly">Топ за неделю</span>
            <span class="nav-item" id="nav-weekly">Топ за месяц</span>-->
        </div>
    </div>
    <div class="container">
        <div class="sub-header-container">
            <div class="update-info-container">
                <label class="update-info-label" id="timeDiff"></label>
            </div>
            <div class="sort-container">
                <label class="sort-label">🔀 Сортировка по</label>
                <select id="sort-dropdown" class="sort-dropdown">
                    <option value="default">рейтингу</option>
                    <option value="pub_date">дате публикации</option>
                    <option value="issue_id">добавлению на HF</option>
                </select>
            </div>
        </div>
        <div class="category-toggle">
            <div class="svg-container">
                <span id="category-toggle">🔍 Фильтр</span>
                <svg height="3" width="200">
                    <line x1="0" y1="0" x2="200" y2="0" 
                        stroke="black" 
                        stroke-width="2" 
                        stroke-dasharray="3, 3" />
                </svg>
            </div>
        </div>
        <div class="category-filters" id="category-filters">
            <span class="clear-categories" id="clear-categories">🧹</span>
            <!-- Categories -->
        </div>
        <main id="articles-container">
            <!-- Articles -->
        </main>
    </div>
    <footer>
        <div class="container">
            <p><a style="color:white;" href="https://t.me/doomgrad">градиент обреченный</a> ✖️ <a style="color:white;" href="https://huggingface.co/papers">hugging face</a></p>
        </div>
    </footer>
    <script>    
        function toggleTheme() {{
            const body = document.body;
            body.classList.toggle('light-theme');
            body.classList.toggle('dark-theme');

            const isDarkMode = body.classList.contains('dark-theme');
            localStorage.setItem('darkMode', isDarkMode);
            
            if (isDarkMode) {{
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{con.TITLE_DARK}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.add('rotate');
            }}  else {{
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{con.TITLE_LIGHT}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.remove('rotate');
            }}
        }}

        const articlesData = {data["papers"]};
        const articlesContainer = document.getElementById('articles-container');
        const sortDropdown = document.getElementById('sort-dropdown');
        const categoryFiltersContainer = document.getElementById('category-filters');
        const categoryToggle = document.getElementById('category-toggle');
        const clearCategoriesButton = document.getElementById('clear-categories');
        let selectedCategories = [];
        let selectedArticles = [];
        let sortBy = 'issue_id';     

        function getUrlParameters() {{
            const urlParams = new URLSearchParams(window.location.search);
            const categoriesParam = urlParams.get('cat');
            let categories = categoriesParam ? categoriesParam.split(',') : [];
            categories = categories.map(element => `#${{element}}`);
            return categories
        }}

        function updateUrlWithCategories() {{
            let cleanedCategories = selectedCategories.map(element => element.replace(/^#/, ''));
            const newUrl = cleanedCategories.length > 0 
                ? `${{window.location.pathname}}?cat=${{cleanedCategories.join(',')}}`
                : window.location.pathname;
            console.log("cleanedCategories", cleanedCategories)
            window.history.pushState({{}}, '', newUrl);
        }}

        function loadSettings() {{
            const isDarkMode = localStorage.getItem('darkMode') === 'true';
            const themeToggle = document.getElementById('theme-toggle');
            let settingSortBy = localStorage.getItem('sort_by');
            const sortDropdown = document.getElementById('sort-dropdown');
            
            if (isDarkMode) {{
                document.body.classList.remove('light-theme');
                document.body.classList.add('dark-theme');
                themeToggle.checked = true;
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{con.TITLE_DARK}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.add('rotate');
            }}

            if ((!settingSortBy) || (settingSortBy === 'null')) {{
                settingSortBy = 'issue_id';
            }}
            
            sortDropdown.value = settingSortBy;
            sortBy = settingSortBy;
        }}

        document.getElementById('theme-toggle').addEventListener('change', toggleTheme);

        function getUniqueCategories(articles) {{
            const categories = new Set();
            articles.forEach(article => {{
                if (article.data && article.data.categories) {{
                    article.data.categories.forEach(cat => categories.add(cat));
                }}
            }});
            let res = Array.from(categories);
            res.sort();
            return res;
        }}
        
        function createCategoryButtons() {{
            const categories = getUniqueCategories(articlesData);
            categories.forEach(category => {{
                const button = document.createElement('span');
                button.textContent = category;
                button.className = 'category-button';
                button.onclick = () => toggleCategory(category, button);
                categoryFiltersContainer.appendChild(button);
            }});
        }}

        function toggleCategory(category, button) {{
            const index = selectedCategories.indexOf(category);
            if (index === -1) {{
                selectedCategories.push(category);
                button.classList.add('active');
            }} else {{
                selectedCategories.splice(index, 1);
                button.classList.remove('active');
            }}         
            filterAndRenderArticles();
            saveCategorySelection();
            updateSelectedArticlesTitle();
            updateUrlWithCategories();
        }}

        function saveCategorySelection() {{
            localStorage.setItem('selectedCategories', JSON.stringify(selectedCategories));
        }}

        function updateSelectedArticlesTitle() {{
            if (selectedArticles.length === articlesData.length) {{
                categoryToggle.textContent = '🏷️ Фильтр';
            }} else {{
                categoryToggle.textContent = `🏷️ Фильтр (${{formatArticlesTitle(selectedArticles.length)}})`;
            }}
        }}

        function cleanCategorySelection() {{
            localStorage.setItem('selectedCategories', JSON.stringify('[]'));
        }}

        function loadCategorySelection() {{
            const urlCategories = getUrlParameters();
            if (urlCategories.length > 0) {{
                selectedCategories = urlCategories;
                saveCategorySelection();
            }} else {{
                const savedCategories = localStorage.getItem('selectedCategories');
                if (savedCategories && savedCategories !== '"[]"') {{
                    selectedCategories = JSON.parse(savedCategories);                    
                }}
            }}
            updateCategoryButtonStates();
        }}

        function updateCategoryButtonStates() {{
            const buttons = categoryFiltersContainer.getElementsByClassName('category-button');
            Array.from(buttons).forEach(button => {{
                if (selectedCategories.includes(button.textContent)) {{
                    button.classList.add('active');
                }} else {{
                    button.classList.remove('active');
                }}
            }});
        }}

        function filterAndRenderArticles() {{
            console.log(selectedCategories);
            let filteredArticles = selectedCategories.length === 0
                ? articlesData
                : articlesData.filter(article => 
                    article.data && article.data.categories && 
                    article.data.categories.some(cat => selectedCategories.includes(cat))
                );

            console.log('filteredArticles', filteredArticles)

            if (filteredArticles.length === 0) {{
                selectedArticles = articlesData;
                selectedCategories = [];
                cleanCategorySelection();
            }} else {{
                selectedArticles = filteredArticles;
            }}

            console.log('selectedArticles', selectedArticles)

            sortArticles(selectedArticles);
        }}

        function clearAllCategories() {{
            selectedCategories = [];
            updateCategoryButtonStates();
            filterAndRenderArticles();
            saveCategorySelection();
            updateSelectedArticlesTitle();
            updateUrlWithCategories();
        }}

        function renderArticles(articles) {{
            console.log(articles);
            articlesContainer.innerHTML = '';
            articles.forEach((item, index) => {{
                if ("error" in item) {{
                    console.log(`Omitting JSON. ${{item["raw_data"]}}`);
                    return;
                }}
                const explanation = item["data"]["desc"];
                const cats = item["data"]["categories"].join(" ");
                const articleHTML = `
                    <article class='x${{item["hash"]}}'>
                        <div class="background-digit">${{index + 1}}</div>
                        <div class="article-content" onclick="toggleAbstract(${{index}})">
                            <h2>${{item['data']['emoji']}} ${{item['title']}}</h2>
                            <p class="meta"><svg class="text-sm peer-checked:text-gray-500 group-hover:text-gray-500" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" role="img" width="1em" height="1em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 12 12"><path transform="translate(0, 2)" fill="currentColor" d="M5.19 2.67a.94.94 0 0 1 1.62 0l3.31 5.72a.94.94 0 0 1-.82 1.4H2.7a.94.94 0 0 1-.82-1.4l3.31-5.7v-.02Z"></path></svg> ${{item['score']}}. ${{item['data']['title']}}</p>
                            <p class="pub-date">📅 Статья от ${{item['pub_date_ru']}}</p>
                            <div id="abstract-${{index}}" class="abstract">
                                <p>${{explanation}}</p>
                                <div id="toggle-${{index}}" class="abstract-toggle">...</div>
                            </div>
                            <div class="links">
                                <a href="${{item['url']}}" target="_blank">Статья</a>
                            </div>
                            <p class="tags">${{cats}}</p>
                        </div>
                    </article>
                `;
                articlesContainer.innerHTML += articleHTML;
            }});
        }}
        
        function sortArticles() {{
            let sortedArticles = [...selectedArticles];
            if (sortBy === 'issue_id') {{
                sortedArticles.sort((a, b) => b.issue_id - a.issue_id);
            }}
            if (sortBy === 'pub_date') {{
                sortedArticles.sort((a, b) => b.pub_date.localeCompare(a.pub_date));
            }}
            renderArticles(sortedArticles);
            localStorage.setItem('sort_by', sortBy);
        }}
        
        sortDropdown.addEventListener('change', (event) => {{
            sortBy = event.target.value;
            sortArticles(event.target.value);
        }});

        categoryToggle.addEventListener('click', () => {{
            categoryFiltersContainer.classList.toggle('expanded');
        }});

        clearCategoriesButton.addEventListener('click', clearAllCategories);
        
        function updateTimeDiffs() {{
            const timeDiff = document.getElementById('timeDiff');
            timeDiff.innerHTML = '🔄 ' + getTimeDiffRu('{data["time_utc"]}');
        }} 
        function hideNextLink() {{
            if (isToday('{data["time_utc"]}')) {{
                const element = document.getElementById('nav-next');
                if (element) {{    
                    element.style.display = 'none';
                }}
            }}
        }}

        loadSettings();
        createCategoryButtons();
        loadCategorySelection();
        filterAndRenderArticles();
        updateSelectedArticlesTitle();
        updateTimeDiffs();
        hideNextLink(); 
    </script>
</body>
</html>
    """
    return html


import json
from datetime import datetime, timezone, timedelta

for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        html_index = make_html(feed)

    html_path = doc.replace("json", "html")

    with open(html_path, "w", encoding="utf-8") as fout:
        fout.write(html_index)

    # break


# %%
