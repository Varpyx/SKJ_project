# Využití AI nástrojů při projektu

## Jaké nástroje AI byly použity
Při řešení této úlohy jsme využili následující nástroje:

* **Claude AI** - hlavní kostra aplikace
* **Gemini** - odladění bugu a chyb

## Příklady promptů
* *"Mame tohle zadání, projdi ho a rozmysli si jak bys ho zpracoval"*
* *"Vytvoř toto zadání jako kod, který si jednoduše spustím"*
* *"Proč mi nejde zobrazit localhost stránka?"*
* *"Důkladně popiš funkčnost a zaměř se na problemy"*

## Co AI vygenerovala správně
* **Kompletně funkční struktura:** Claude AI na první prompt dokazal vygenerovat funčkní program, vygeneroval i requirements.txt pro jednoduché lokální nasazení.


## Jaké chyby AI udělala a co bylo nutné opravit
* **Špatná verze databáze:** Zadal původně špatnou verzi SQLAlchemy do requirements.txt - bylo nutné stáhnout novější verzi, poté již vše funkční

