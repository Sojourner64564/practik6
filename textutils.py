"""Нормализация текста, стоп-слова, лемматизация (pymorphy3)."""
import re
from functools import lru_cache

try:
    import pymorphy3
    _MORPH = pymorphy3.MorphAnalyzer()
except Exception:  # pymorphy3 не установлен — работаем без лемматизации
    _MORPH = None

TOKEN_RE = re.compile(r"[a-zа-я0-9]+")

STOP_WORDS = set("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из
ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам сказал ведь там потом себя
ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда
кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда
можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя
впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это просто очень
вообще значит короче сегодня вот типа также который которые которая которое свои своей своих наш наша наши ваш ваша
""".split())

# COCO-классы YOLO -> русские названия (первое слово — основное, остальные — синонимы)
OBJECT_NAMES_RU = {
    "person": "человек люди", "bicycle": "велосипед", "car": "автомобиль машина", "motorcycle": "мотоцикл",
    "bus": "автобус", "train": "поезд", "truck": "грузовик", "boat": "лодка", "bird": "птица",
    "cat": "кошка кот", "dog": "собака", "horse": "лошадь", "backpack": "рюкзак", "umbrella": "зонт",
    "handbag": "сумка", "suitcase": "чемодан", "bottle": "бутылка", "wine glass": "бокал", "cup": "чашка кружка",
    "fork": "вилка", "knife": "нож", "spoon": "ложка", "bowl": "миска тарелка", "banana": "банан", "apple": "яблоко",
    "sandwich": "бутерброд", "orange": "апельсин", "pizza": "пицца", "cake": "торт", "chair": "стул кресло",
    "couch": "диван", "potted plant": "растение цветок", "bed": "кровать", "dining table": "стол",
    "toilet": "унитаз туалет", "tv": "телевизор", "laptop": "ноутбук", "mouse": "мышь", "remote": "пульт",
    "keyboard": "клавиатура", "cell phone": "телефон смартфон", "microwave": "микроволновка", "oven": "духовка печь",
    "toaster": "тостер", "sink": "раковина мойка", "refrigerator": "холодильник", "book": "книга",
    "clock": "часы", "vase": "ваза", "scissors": "ножницы", "tie": "галстук", "sports ball": "мяч",
    "traffic light": "светофор", "bench": "скамейка лавка", "skateboard": "скейтборд", "tennis racket": "ракетка",
}


def normalize(text: str) -> str:
    return (text or "").lower().replace("ё", "е")


@lru_cache(maxsize=50000)
def lemma(word: str) -> str:
    w = normalize(word)
    if _MORPH is None or not re.fullmatch(r"[а-я]+", w):
        return w
    try:
        return normalize(_MORPH.parse(w)[0].normal_form)
    except Exception:
        return w


def tokens(text: str) -> list:
    out = []
    for t in TOKEN_RE.findall(normalize(text)):
        if len(t) < 2 or t.isdigit() or t in STOP_WORDS:
            continue
        out.append(t)
    return out


def lemmas(text: str) -> list:
    out = []
    for t in tokens(text):
        l = lemma(t)
        if len(l) >= 3 and l not in STOP_WORDS:
            out.append(l)
    return out


def label_ru(cls: str) -> str:
    return OBJECT_NAMES_RU.get(cls, cls).split()[0]


def object_names(cls: str) -> str:
    """Все имена класса (en + ru-синонимы) для поиска."""
    return f"{cls} {OBJECT_NAMES_RU.get(cls, '')}".strip()
