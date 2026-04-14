# Využití AI nástrojů při projektu

## Jaké nástroje AI byly použity
Při řešení této úlohy jsme využili následující nástroje:

* **Gemini** - setupnutí 1. a 2. ukolu 
* **Claude AI** - hlavní kostra aplikace

## Příklady promptů
* *"Jak pracovat s alembic?"*
* *"Proč alembic upgrade head vrací tuto chybu?"*
* *"Doplň do SQLAlchemy modelu Bucket sloupec bandwidth_bytes a vygeneruj k němu novou migraci."*
* *"Uprav upload a download endpointy tak, aby u daného bucketu přičítaly velikost souboru do bandwidth_bytes."*


## Co AI vygenerovala správně
* **Správný kod pro bucket**
* **2 nove endpointy pro vytvoření a vypis filu v bucketu**
* **Rozšíření endpointů: vygenerovala a rozšířila endpointy pro správu bucketů billing a objects**
* **Filtr pro soft delete v endpointech**

## Jaké chyby AI udělala a co bylo nutné opravit
* **Neřekl mi že musíme smazat puvodní db aby alempic fungoval**

