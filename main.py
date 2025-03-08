"""
Telegram Bot for OMG: Das Partyspiel für Furchtlose

This bot runs a game where players answer questions from selected decks.
It supports two languages (Russian and English) and tracks game state and statistics.
@SholderF
"""

import time
import random
import pandas as pd
from telebot import TeleBot, types
from typing import Any, Dict, List, Set

# --- Configuration & Global State ---

TOKEN = 'YOUR_BOT_TOKEN_HERE'
bot: TeleBot = TeleBot(TOKEN)

# Global game state
game_state: Dict[str, Any] = {
    "start_game_time": 0.0,
    "end_game_time": 0.0,
    "players": [],
    "player_turn": 0,
    "selected_decks": [],
    "decks": {},  # Each deck is a list of cards (each card is a dict with keys 'question' and 'sip')
    "player_used_questions": {},  # {player: {deck: set(indices)}}
    "stats": {},  # {player: {"player_time": float, "sips": int, "answered": int, "regenerated": int}}
    "language": "ru"  # default language
}

# Multi-language texts
texts: Dict[str, str] = {
    "start_lang": "Выберите язык / Select language:",
    "welcome_ru": ("Добро пожаловать в OMG: Das Partyspiel für Furchtlose на русском!\n"
                   "Пожалуйста, введите имена игроков (через запятую):"),
    "welcome_en": ("Welcome to OMG: Das Partyspiel für Furchtlose on english!\n"
                   "Please enter the players' names (separated by commas):"),
    "choose_deck_ru": ("Выберите колоду (колоды). Нажмите ещё раз, чтобы отменить выбор. "
                       "Когда закончите, нажмите «Готово»."),
    "choose_deck_en": ("Choose deck(s). Tap again to deselect. When finished, press 'Done'."),
    "no_deck_ru": "Пожалуйста, выберите хотя бы одну колоду!",
    "no_deck_en": "Please choose at least one deck!",
    "deck_selected_ru": "Выбор колоды завершён!",
    "deck_selected_en": "Deck selection completed!",
    "card_text_ru": (
        "\n══════ 🎲 OMG Party Game 🎲 ══════\n\n"
        "🎭 <b>Игрок:</b> {player}\n\n"
        "📜 <b>Вопрос:</b>\n"
        "🔥 <i>{question}</i> 🔥\n\n"
        "🍺 <b>Количество глотков:</b> {sip}\n\n"
        "══════ 🎲 OMG Party Game 🎲 ══════\n"
    ),
    "card_text_en": (
        "\n══════ 🎲 OMG Party Game 🎲 ══════\n\n"
        "🎭 <b>Player:</b> {player}\n\n"
        "📜 <b>Question:</b>\n"
        "🔥 <i>{question}</i> 🔥\n\n"
        "🍺 <b>Sips to Take:</b> {sip}\n\n"
        "══════ 🎲 OMG Party Game 🎲 ══════\n"
    ),
    "answer_ru": "Ответить 🎤️",
    "answer_en": "Answer 🎤",
    "drink_ru": "Выпить 🍻",
    "drink_en": "Drink 🍻",
    "regenerate_ru": "Заменить карту 🎲",
    "regenerate_en": "Play another card 🎲",
    "end_game_ru": "Закончить игру 🏁",
    "end_game_en": "Finish the game 🏁",
    "no_more_card_ru": "Для {player} больше нет вопросов ни в одной из колод.",
    "no_more_card_en": "No more questions available for {player} in any deck.",
    "questions_exhausted_ru": "Вопросы исчерпаны. Спасибо за игру!.",
    "questions_exhausted_en": "Questions exhausted. Thanks for playing!",
    "final_stats_ru": "Игра завершена! Спасибо за игру!",
    "final_stats_en": "Game over! Thanks for playing!",
    "stats_button_ru": "Показать статистику последней игры",
    "stats_button_en": "Show last game's statistics",
    "done_ru": "Готово",
    "done_en": "Done"
}


# --- Utility Functions ---

def get_text(key: str, **kwargs) -> str:
    """
    Retrieve localized text based on the current language.
    """
    lang = game_state.get("language", "ru")
    text = texts.get(f"{key}_{lang}", texts.get(key))
    return text.format(**kwargs)


def format_time(seconds: float) -> str:
    """
    Format seconds into a human-readable string based on the current language.
    """
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: List[str] = []
    if game_state.get("language", "ru") == "ru":
        if hours:
            parts.append(f"{hours} ч")
        if minutes:
            parts.append(f"{minutes} мин")
        parts.append(f"{secs} сек")
    else:
        if hours:
            parts.append(f"{hours} h")
        if minutes:
            parts.append(f"{minutes} min")
        parts.append(f"{secs} sec")
    return ", ".join(parts)


def number_to_emoji(sip: Any) -> str:
    """
    Convert a numerical sip value to its corresponding emoji.
    """
    emoji_map = {'1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣'}
    return emoji_map.get(str(sip), '1')


# --- Game Logic Functions ---

def get_decks() -> List[str]:
    """
    Return available deck names based on the current language.
    """
    return ["questions", "actions"] if game_state.get("language", "ru") == "en" else ["вопросы", "действия"]


def load_deck(deck_name: str) -> List[Dict[str, Any]]:
    """
    Load a deck CSV file and return a list of cards.
    """
    df = pd.read_csv(f"decks/{deck_name}.csv", sep='\t')
    return df.to_dict("records")


def selection_deck_markup() -> types.InlineKeyboardMarkup:
    """
    Create an inline keyboard markup for deck selection.
    """
    markup = types.InlineKeyboardMarkup()
    for deck in get_decks():
        button_text = deck.capitalize()
        if deck in game_state["selected_decks"]:
            button_text += " ✅"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"deck_{deck}"))
    markup.add(types.InlineKeyboardButton(get_text("done"), callback_data="deck_done"))
    return markup


def game_has_available_questions() -> bool:
    """
    Check if there are still available questions for any player in any selected deck.
    """
    for player in game_state["players"]:
        for deck in game_state["selected_decks"]:
            deck_cards = game_state["decks"][deck]
            used: Set[int] = game_state["player_used_questions"][player].get(deck, set())
            if len(used) < len(deck_cards):
                return True
    return False


def send_final_stats(chat_id: int) -> None:
    """
    Calculate overall game stats and send them to the chat.
    """
    game_state["end_game_time"] = time.time()
    final_text = get_text("final_stats")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_text("stats_button"), callback_data="statistics"))
    bot.send_message(chat_id, final_text, reply_markup=markup)


def send_card(chat_id: int) -> None:
    """
    Select and send a random card for the current player.
    """
    player = game_state["players"][game_state["player_turn"]]
    available_decks: List[Any] = []

    # Gather decks with available questions for the player
    for deck in game_state["selected_decks"]:
        deck_cards = game_state["decks"][deck]
        used: Set[int] = game_state["player_used_questions"][player].get(deck, set())
        available_indices = [idx for idx in range(len(deck_cards)) if idx not in used]
        if available_indices:
            available_decks.append((deck, available_indices))

    # If no decks have available questions, prompt to skip or end game
    if not available_decks:
        markup = types.InlineKeyboardMarkup()
        next_text = "Следующий игрок" if game_state["language"] == "ru" else "Next player"
        markup.add(types.InlineKeyboardButton(next_text + " ➡️", callback_data="skip_player"))
        markup.add(types.InlineKeyboardButton(get_text("end_game"), callback_data="end_game"))
        bot.send_message(chat_id, get_text("no_more_card", player=player))
        return

    # Start the turn timer if not already started
    if "current_turn_start" not in game_state["stats"][player]:
        game_state["stats"][player]["current_turn_start"] = time.time()

    # Randomly select a deck and card
    deck_choice, available_indices = random.choice(available_decks)
    card_index = random.choice(available_indices)

    # Mark the card as used for this player
    if deck_choice not in game_state["player_used_questions"][player]:
        game_state["player_used_questions"][player][deck_choice] = set()
    game_state["player_used_questions"][player][deck_choice].add(card_index)

    # Store current card details for later reference
    game_state["current_card"] = {"player": player, "deck": deck_choice, "card_index": card_index}
    card = game_state["decks"][deck_choice][card_index]

    message_text = get_text("card_text", player=player, question=card['question'],
                            sip=number_to_emoji(card['sip']))

    # Build the response buttons
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(get_text("answer"), callback_data="answer"),
        types.InlineKeyboardButton(get_text("drink"), callback_data="drink")
    )
    markup.row(
        types.InlineKeyboardButton(get_text("regenerate"), callback_data="regenerate"),
        types.InlineKeyboardButton(get_text("end_game"), callback_data="end_game")
    )

    bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="HTML")


def end_current_turn(player: str) -> None:
    """
    Ends the current player's turn by updating the total elapsed time.
    """
    current_stats = game_state["stats"][player]
    if "current_turn_start" in current_stats:
        elapsed = time.time() - current_stats.pop("current_turn_start")
        current_stats["player_time"] += elapsed


# --- Telegram Handlers ---

@bot.message_handler(commands=["start"])
def start_command(message: types.Message) -> None:
    """
    Handle the /start command by showing a language selection keyboard.
    """
    markup = types.InlineKeyboardMarkup()
    ru_button = types.InlineKeyboardButton("RU", callback_data="lang_ru")
    en_button = types.InlineKeyboardButton("EN", callback_data="lang_en")
    markup.add(ru_button, en_button)
    bot.send_message(message.chat.id, texts["start_lang"], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def language_selection_callback(call: types.CallbackQuery) -> None:
    """
    Process language selection and prompt the user to enter player names.
    """
    selected_lang = call.data.split("_")[1]
    game_state["language"] = selected_lang
    welcome_text = texts["welcome_ru"] if selected_lang == "ru" else texts["welcome_en"]
    bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(call.message, initialize_game)


@bot.callback_query_handler(func=lambda call: call.data.startswith("deck_"))
def deck_selection_callback(call: types.CallbackQuery) -> None:
    """
    Handle deck selection or finalization.
    """
    chat_id = call.message.chat.id
    if call.data == "deck_done":
        if not game_state["selected_decks"]:
            bot.answer_callback_query(call.id, get_text("no_deck"))
            return
        for deck in game_state["selected_decks"]:
            game_state["decks"][deck] = load_deck(deck)
        bot.edit_message_text(get_text("deck_selected"), chat_id, call.message.message_id)
        send_card(chat_id)
    else:
        # Toggle deck selection
        deck = call.data.replace("deck_", "")
        if deck in game_state["selected_decks"]:
            game_state["selected_decks"].remove(deck)
        else:
            game_state["selected_decks"].append(deck)
        markup = selection_deck_markup()
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["answer", "drink", "regenerate", "end_game", "skip_player"])
def callback_handler(call: types.CallbackQuery) -> None:
    """
    Process gameplay callbacks for answering, drinking, regenerating a card,
    skipping a player, or ending the game.
    """
    chat_id = call.message.chat.id
    player = game_state["players"][game_state["player_turn"]]

    if call.data in ["answer", "drink"]:
        if call.data == "drink":
            # Add sip count to player's stats
            deck_choice = game_state["current_card"]["deck"]
            card_index = game_state["current_card"]["card_index"]
            card = game_state["decks"][deck_choice][card_index]
            game_state["stats"][player]["sips"] += card["sip"]
        else:
            game_state["stats"][player]["answered"] += 1

        end_current_turn(player)
        game_state["player_turn"] = (game_state["player_turn"] + 1) % len(game_state["players"])
        send_card(chat_id)

    elif call.data == "regenerate":
        game_state["stats"][player]["regenerated"] += 1
        send_card(chat_id)

    elif call.data == "skip_player":
        game_state["player_turn"] = (game_state["player_turn"] + 1) % len(game_state["players"])
        if not game_has_available_questions():
            bot.send_message(chat_id, get_text("questions_exhausted"))
            send_final_stats(chat_id)
            return
        send_card(chat_id)

    elif call.data == "end_game":
        end_current_turn(player)
        send_final_stats(chat_id)


@bot.callback_query_handler(func=lambda call: call.data == "statistics")
def callback_handler_statistics(call: types.CallbackQuery) -> None:
    """
    Generate and send a statistics table for the last game.
    """
    chat_id = call.message.chat.id
    headers = ["Игрок", "Время", "Глотки", "Вопросы", "Замен"] if game_state.get("language", "ru") == "ru" else \
        ["Player", "Time", "Sips", "Questions", "Replacements"]

    col_widths = [len(header) for header in headers]
    rows: List[List[str]] = []

    # Build stats rows for each player
    for player in game_state["players"]:
        stats = game_state["stats"][player]
        time_str = format_time(stats['player_time'])
        row = [
            player,
            time_str,
            str(stats['sips']),
            str(stats['answered']),
            str(stats['regenerated'])
        ]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Helper to create a table line
    def make_line(cells: List[str]) -> str:
        return " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(cells))

    header_line = make_line(headers)
    separator_line = "-+-".join('-' * col_width for col_width in col_widths)
    table_lines = [header_line, separator_line]
    for row in rows:
        table_lines.append(make_line(row))

    overall_time = format_time(game_state["end_game_time"] - game_state["start_game_time"])
    overall_line = f"Общее время в игре: {overall_time}" if game_state.get("language", "ru") == "ru" \
        else f"Total game time: {overall_time}"
    table_lines.extend(["", overall_line])

    final_stats = "```\n" + "\n".join(table_lines) + "\n```"
    bot.send_message(chat_id, final_stats, parse_mode="Markdown")


def initialize_game(message: types.Message) -> None:
    """
    Initialize game state with player names and start deck selection.
    """
    names = [name.strip() for name in message.text.split(",")]
    game_state["players"] = names
    game_state["player_turn"] = 0
    game_state["selected_decks"] = []
    game_state["start_game_time"] = time.time()

    # Initialize per-player game state and stats
    for name in names:
        game_state["player_used_questions"][name] = {}
        game_state["stats"][name] = {
            "player_time": 0,
            "sips": 0,
            "answered": 0,
            "regenerated": 0
        }
    send_deck_selection(message.chat.id)


def send_deck_selection(chat_id: int) -> None:
    """
    Prompt the user to select decks.
    """
    markup = selection_deck_markup()
    bot.send_message(chat_id, get_text("choose_deck"), reply_markup=markup)


# --- Main Execution ---

if __name__ == "__main__":
    bot.polling()
