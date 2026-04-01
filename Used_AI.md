# Využití AI nástrojů při projektu

## Jaké nástroje AI byly použity
Při řešení této úlohy jsme využili následující nástroje:

* **Claude AI** - hlavní kostra aplikace

## Příklady promptů
* *"Vysvětli mi knihovny pydantic"*
* *"Proč mi nefunguje validace dat?"*
* *"Jaký je rozdíl mezi běžným Python dict a Pydantic BaseModel?"*
* *"Uprav existující Pydantic model tak, aby validoval všechna data"*
* *"Jak funguje Field a jaké má parametry?"*


## Co AI vygenerovala správně
* **Správný kod pro checkování dat**
* **Rozšíření aplikace o nové funkce v databázi**
* **Rozdělení kodu do souborů a udržení čístého kodu s komentáři**


## Jaké chyby AI udělala a co bylo nutné opravit
* **Špatně napsané validátory** - původně použil starý styl (z Pydantic v2) - na druhý prompt již věděl kde je chyba
* **Zapomněl na užití Field** - po připomenutí ho doplnil

