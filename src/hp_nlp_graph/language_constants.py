STOP_WORDS = [  # words to be removed from the text
    "of",
    "the",
    "at",
    "family",
    "keeper",
    "wizard",
    "fat",
    "de",
    "hogwarts",
    "hotel",
    "owner",
    "express",
    "and",
    "witch",
    "who",
]

# Character titles with these words will not be matched
REMOVE_WORDS = [
    "wizard",
    "Wizard",
    "witch",
    "Witch",
    "director",
    "at",
    "of",
    "owner",
    "family",
    "Unidentified",
    "conductor",
    "Goblin",
    "Squid",
    "ghoul",
    "and",
    "Salamander",
    "ghost",
    "Ghost",
    "Transylvania",
    "colony",
    "saleswoman",
    "Dementor",
    "herd",
    "Boggart",
    "Troll",
    "Hangleton",
    "House",
    "Academy",
    "postman",
    "Omnioculars",
    "Veela",
    "children",
    "Hogwarts",
    "Sisters",
    "sisters",
    "Unicorn",
    "Lake",
    "Maze",
    "Place",
    "Nottingham",
    "Girl",
    "Member",
    "Inferius",
    "official",
    "peacock",
    "boy",
    "cat",
    "Department",
    "woman",
    "brothers",
    "Wandless",
    # words with "'" such as "Piers Polkiss's mother"
]

SHORT_FORMS = {
    "Ronald": "ron",
    "William": "bill",
    "Charles": "charlie",
    "Percy": "perce",
    "Ginevra": "ginny",
}