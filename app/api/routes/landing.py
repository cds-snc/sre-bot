"""Landing page route for SRE Bot.

Provides a simple, accessible, bilingual landing page informing users
that the SRE Bot frontend has been moved to Backstage.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Landing"])

# Load content from JSON file
CONTENT_PATH = Path(__file__).parent / "landing_content.json"
with open(CONTENT_PATH) as f:
    LANDING_CONTENT = json.load(f)


LANDING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="SRE Bot API - Service management has moved to Backstage">
    <title id="page-title">SRE Bot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary-color: #0051BA;
            --secondary-color: #1E3A8A;
            --text-dark: #1F2937;
            --text-light: #6B7280;
            --bg-light: #F9FAFB;
            --border-color: #E5E7EB;
            --focus-color: #0051BA;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-dark);
            background: linear-gradient(135deg, var(--bg-light) 0%, #FFFFFF 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        main {
            max-width: 800px;
            width: 100%;
        }

        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            padding: 60px 40px;
            text-align: center;
        }

        .language-toggle {
            position: absolute;
            top: 20px;
            right: 20px;
        }

        .toggle-btn {
            background: var(--primary-color);
            color: white;
            border: 2px solid var(--primary-color);
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        .toggle-btn:hover {
            background: var(--secondary-color);
            border-color: var(--secondary-color);
        }

        .toggle-btn:focus {
            outline: 3px solid var(--focus-color);
            outline-offset: 2px;
        }

        .header {
            margin-bottom: 40px;
        }

        .logo {
            font-size: 48px;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 10px;
        }

        h1 {
            font-size: 32px;
            font-weight: 700;
            color: var(--text-dark);
            margin-bottom: 16px;
            line-height: 1.2;
        }

        .subtitle {
            font-size: 18px;
            color: var(--text-light);
            margin-bottom: 40px;
            font-weight: 400;
        }

        .content {
            text-align: left;
            margin: 40px 0;
        }

        .content-section {
            margin-bottom: 32px;
        }

        .content-section h2 {
            font-size: 20px;
            font-weight: 600;
            color: var(--secondary-color);
            margin-bottom: 12px;
        }

        .content-section p {
            font-size: 16px;
            color: var(--text-light);
            line-height: 1.8;
            margin-bottom: 12px;
        }

        .links {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-top: 24px;
        }

        .link-btn {
            display: inline-block;
            padding: 14px 28px;
            background: var(--primary-color);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.3s ease;
            border: 2px solid var(--primary-color);
        }

        .link-btn:hover {
            background: var(--secondary-color);
            border-color: var(--secondary-color);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 81, 186, 0.3);
        }

        .link-btn:focus {
            outline: 3px solid var(--focus-color);
            outline-offset: 2px;
        }

        .link-secondary {
            background: transparent;
            color: var(--primary-color);
            border: 2px solid var(--primary-color);
        }

        .link-secondary:hover {
            background: var(--bg-light);
            border-color: var(--secondary-color);
            color: var(--secondary-color);
        }

        .info-box {
            background: var(--bg-light);
            border-left: 4px solid var(--primary-color);
            padding: 20px;
            border-radius: 6px;
            margin-top: 32px;
            text-align: left;
        }

        .info-box h3 {
            font-size: 16px;
            font-weight: 600;
            color: var(--secondary-color);
            margin-bottom: 8px;
        }

        .info-box p {
            font-size: 14px;
            color: var(--text-light);
            line-height: 1.6;
        }

        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            font-size: 14px;
            color: var(--text-light);
        }

        .skip-link {
            position: absolute;
            top: -40px;
            left: 0;
            background: var(--primary-color);
            color: white;
            padding: 8px;
            text-decoration: none;
            z-index: 100;
        }

        .skip-link:focus {
            top: 0;
        }

        @media (max-width: 640px) {
            .container {
                padding: 40px 24px;
            }

            h1 {
                font-size: 24px;
            }

            .subtitle {
                font-size: 16px;
            }

            .logo {
                font-size: 36px;
            }

            .language-toggle {
                position: static;
                margin-bottom: 20px;
                text-align: right;
            }

            .links {
                flex-direction: column;
            }

            .link-btn {
                width: 100%;
                text-align: center;
            }
        }

        @media print {
            body {
                background: white;
            }

            .container {
                box-shadow: none;
            }

            .language-toggle,
            .link-btn {
                display: none;
            }
        }

        @media (prefers-contrast: more) {
            :root {
                --primary-color: #0039A6;
                --secondary-color: #001A4D;
                --text-dark: #000000;
            }

            .container {
                border: 2px solid var(--text-dark);
            }
        }

        @media (prefers-reduced-motion: reduce) {
            * {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }
    </style>
</head>
<body>
    <a href="#main" class="skip-link">Skip to main content</a>

    <div class="language-toggle">
        <button class="toggle-btn" id="langToggle" aria-label="Toggle language">
            <span id="toggleLabel">Français</span>
        </button>
    </div>

    <main id="main">
        <div class="container">
            <div class="header">
                <div class="logo" id="logo">🤖 SRE Bot</div>
                <h1 id="heading">Service Management Evolved</h1>
                <p class="subtitle" id="subtitle">Your SRE Bot frontend has moved to Backstage</p>
            </div>

            <div class="content" id="content">
                <!-- Content sections will be inserted here -->
            </div>

            <div class="links" id="links">
                <!-- Links will be inserted here -->
            </div>

            <div class="info-box">
                <h3 id="helpHeading">Need Help?</h3>
                <p id="helpContent">For questions or issues, please reach out to the SRE team.</p>
            </div>

            <div class="footer">
                <p id="footer">SRE Bot API v1.0 • Powered by FastAPI</p>
            </div>
        </div>
    </main>

    <script>
        // Content data will be injected here
        const LANDING_CONTENT = CONTENT_DATA;

        const htmlElement = document.documentElement;
        const langToggle = document.getElementById('langToggle');
        const toggleLabel = document.getElementById('toggleLabel');

        // Initialize language from localStorage or default to English
        const savedLang = localStorage.getItem('sre-bot-lang') || 'en';
        let currentLang = savedLang;
        htmlElement.lang = currentLang;

        // Render content for the given language
        function renderContent(lang) {
            const content = LANDING_CONTENT[lang];

            // Update page title
            document.getElementById('page-title').textContent = content.title;
            document.title = content.title;

            // Update header
            document.getElementById('logo').textContent = content.logo;
            document.getElementById('heading').textContent = content.heading;
            document.getElementById('subtitle').textContent = content.subtitle;

            // Update toggle button
            toggleLabel.textContent = content.toggle_button;
            langToggle.setAttribute('aria-label', content.toggle_aria_label);

            // Clear and render content sections
            const contentDiv = document.getElementById('content');
            contentDiv.innerHTML = '';
            content.sections.forEach(section => {
                const sectionEl = document.createElement('div');
                sectionEl.className = 'content-section';
                sectionEl.innerHTML = `
                    <h2>${section.heading}</h2>
                    <p>${section.content}</p>
                `;
                contentDiv.appendChild(sectionEl);
            });

            // Clear and render links
            const linksDiv = document.getElementById('links');
            linksDiv.innerHTML = '';
            content.links.forEach(link => {
                const linkEl = document.createElement('a');
                linkEl.href = link.href;
                linkEl.textContent = link.label;
                linkEl.className = 'link-btn' + (link.secondary ? ' link-secondary' : '');
                if (link.external) {
                    linkEl.target = '_blank';
                    linkEl.rel = 'noopener noreferrer';
                }
                linksDiv.appendChild(linkEl);
            });

            // Update help section
            document.getElementById('helpHeading').textContent = content.help_heading;
            document.getElementById('helpContent').innerHTML = content.help_content;

            // Update footer
            document.getElementById('footer').textContent = content.footer;
        }

        // Initial render
        renderContent(currentLang);

        // Language toggle handler
        langToggle.addEventListener('click', () => {
            currentLang = currentLang === 'en' ? 'fr' : 'en';
            htmlElement.lang = currentLang;
            localStorage.setItem('sre-bot-lang', currentLang);
            renderContent(currentLang);

            // Announce language change to screen readers
            const announcement = document.createElement('div');
            announcement.setAttribute('role', 'status');
            announcement.setAttribute('aria-live', 'polite');
            announcement.textContent = LANDING_CONTENT[currentLang].language_changed_announcement;
            announcement.style.position = 'absolute';
            announcement.style.left = '-10000px';
            document.body.appendChild(announcement);
            setTimeout(() => announcement.remove(), 1000);
        });

        // Keyboard support
        langToggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                langToggle.click();
            }
        });
    </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """
    Landing page for SRE Bot.

    Serves a bilingual, accessible landing page informing users that
    the SRE Bot frontend has moved to Backstage.

    Returns:
        HTMLResponse: Bilingual HTML landing page with English/French support
    """
    # Inject the content data as JavaScript
    html_with_content = LANDING_PAGE_HTML.replace(
        "const LANDING_CONTENT = CONTENT_DATA;",
        f"const LANDING_CONTENT = {json.dumps(LANDING_CONTENT)};",
    )
    return HTMLResponse(content=html_with_content)
