from flask import Flask, render_template, request, session, jsonify, redirect, url_for
import openai
import requests
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-secret-key-here")

openai.api_key = "OPENAI_API_KEY" 
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "UNSPLASH_ACCESS_KEY")


TRANSLATIONS = {
    'en': {
        'title': 'Moodboard',
        'search_placeholder': 'For example: winter aesthetic 2025',
        'search_button': 'Search',
        'ai_suggests': 'AI suggests:',
        'voice_search': 'Voice search',
        'favorites': 'Favorites'
    },
    'ru': {
        'title': 'Moodboard',
        'search_placeholder': 'Например: winter aesthetic 2025',
        'search_button': 'Найти',
        'ai_suggests': 'AI предлагает:',
        'voice_search': 'Голосовой поиск',
        'favorites': 'Избранное'
    },
    'kk': {
        'title': 'Moodboard',
        'search_placeholder': 'Мысалы: winter aesthetic 2025',
        'search_button': 'Іздеу',
        'ai_suggests': 'AI ұсынады:',
        'voice_search': 'Дауыстық іздеу',
        'favorites': 'Таңдаулылар'
    }
}


def get_ai_ideas(query, lang='en'):
    """ИИ-подсказки для тегов/поиска."""
    if not query:
        return []
    try:
        prompts = {
            'en': "You are a creative designer. Based on the user's query, suggest 3 short, aesthetic search queries for finding photos. Return only them separated by commas.",
            'ru': "Ты креативный дизайнер. На основе запроса пользователя предложи 3 коротких, эстетичных поисковых запроса для поиска фото. Верни только их через запятую.",
            'kk': "Сіз шығармашыл дизайнерсіз. Пайдаланушының сұрауы негізінде фотосуреттерді іздеу үшін 3 қысқа, эстетикалық іздеу сұрауларын ұсыныңыз. Тек оларды үтірмен бөліп қайтарыңыз."
        }

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompts.get(lang, prompts['en'])},
                {"role": "user", "content": f"Тема: {query}"}
            ]
        )

        content = response.choices[0].message.content
        ideas = [x.strip() for x in content.split(',') if x.strip()]
        return ideas
    except Exception as e:
        print(f"Ошибка AI: {e}")
        return [query]


def search_images(query):
    """Поиск картинок на Unsplash по тексту/тегам."""
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "client_id": UNSPLASH_ACCESS_KEY,
        "per_page": 20,
        "orientation": "portrait"
    }
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        return resp.json().get('results', [])
    print("Unsplash error", resp.status_code, resp.text)
    return []


@app.route('/', methods=['GET', 'POST'])
def index():
    current_lang = session.get('lang', 'en')
    if request.args.get('lang'):
        current_lang = request.args.get('lang')
        if current_lang in TRANSLATIONS:
            session['lang'] = current_lang

    images = []
    ideas = []
    search_query = ""

    if request.method == 'POST':
        # Пользовательский запрос из строки поиска
        search_query = (request.form.get('search') or "").strip()

        # ИИ-подсказки (для отображения тегов под строкой поиска)
        ideas = get_ai_ideas(search_query, current_lang)

        # Здесь НЕ добавляем "aesthetic images" автоматически,
        # чтобы поиск по тегам работал честно
        final_query = search_query if search_query else "trending"
        images = search_images(final_query)
    else:
        # Первый заход / GET без поиска: показываем стартовые картинки
        # можно поменять "trending" на что-нибудь своё: "winter 2025", "design", "abstract" и т.п.
        default_query = "trending"
        images = search_images(default_query)

    # favorites из сессии (список словарей)
    favorites = session.get('favorites', [])
    translations = TRANSLATIONS.get(current_lang, TRANSLATIONS['en'])

    return render_template(
        'index.html',
        images=images,
        ideas=ideas,
        query=search_query,
        translations=translations,
        current_lang=current_lang,
        favorites=favorites
    )


@app.route('/favorite', methods=['POST'])
def favorite_toggle():
    """
    Ожидает JSON:
    { "id": "", "url": "", "link": "", "user": "", "likes": , "alt": "" }
    Возвращает: { "status": "added" / "removed", "favorites_count": n }
    """
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({"error": "invalid data"}), 400

    favs = session.get('favorites', [])

    # ищем по id
    existing = next((f for f in favs if f.get('id') == data['id']), None)

    if existing:
        # удалить
        favs = [f for f in favs if f.get('id') != data['id']]
        session['favorites'] = favs
        session.modified = True
        return jsonify({"status": "removed", "favorites_count": len(favs)})
    else:
        # добавить (сохраняем минимальный набор полей)
        item = {
            "id": data.get('id'),
            "url": data.get('url'),
            "link": data.get('link'),
            "user": data.get('user'),
            "likes": data.get('likes', 0),
            "alt": data.get('alt', '')
        }
        favs.append(item)
        session['favorites'] = favs
        session.modified = True
        return jsonify({"status": "added", "favorites_count": len(favs)})


@app.route('/clear_favorites', methods=['POST'])
def clear_favorites():
    session['favorites'] = []
    session.modified = True
    return redirect(url_for('index'))

@app.route('/chat', methods=['POST'])
def chat():
    """Обработка сообщений чата с AI."""
    data = request.get_json()
    user_message = data.get('message', '')
    # Получаем язык из сессии или fallback на 'en'
    lang = session.get('lang', 'en')
    
    if not user_message:
        return jsonify({'reply': ''})

    # Настройка личности ассистента
    system_prompts = {
        'en': "You are a creative AI assistant for a Moodboard app. Help users find aesthetic ideas, search queries, and color palettes. Keep answers concise and inspiring.",
        'ru': "Ты креативный AI-ассистент для приложения Moodboard. Помогай пользователям находить эстетичные идеи, поисковые запросы и цветовые палитры. Отвечай кратко и вдохновляюще.",
        'kk': "Сіз Moodboard қолданбасына арналған шығармашылық AI көмекшісісіз. Пайдаланушыларға эстетикалық идеяларды, іздеу сұрауларын және түстер палитрасын табуға көмектесіңіз."
    }

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompts.get(lang, system_prompts['en'])},
                {"role": "user", "content": user_message}
            ]
        )
        reply = response.choices[0].message.content
        return jsonify({'reply': reply})
    except Exception as e:
        print(f"Chat error: {e}")
        error_msgs = {
            'en': "Sorry, I'm having trouble connecting right now.",
            'ru': "Извините, сейчас есть проблемы с соединением.",
            'kk': "Кешіріңіз, қазір байланыс орнату қиын болып тұр."
        }
        return jsonify({'reply': error_msgs.get(lang, error_msgs['en'])})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
