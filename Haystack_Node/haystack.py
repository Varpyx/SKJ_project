import os
import threading


class HaystackManager:
    def __init__(self, storage_dir="volumes", max_size_mb=10):
        self.storage_dir = storage_dir
        # Převedeme MB na bajty (pro testování je 10 MB ideální, aby se rotace ukázala brzy)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_volume_id = 1
        self.file_handler = None
        self.current_size = 0

        # Zámek pro thread-safety (kdyby náhodou přišlo více fotek přesně ve stejnou milisekundu)
        self.lock = threading.Lock()

        # Vytvoření složky, pokud neexistuje
        os.makedirs(self.storage_dir, exist_ok=True)
        self._init_latest_volume()

    def _init_latest_volume(self):
        """Najde poslední existující svazek a otevře ho pro přidávání, nebo vytvoří nový."""
        existing_files = [f for f in os.listdir(self.storage_dir) if f.startswith("volume_") and f.endswith(".dat")]

        if existing_files:
            # Vytáhne čísla z názvů (např. z "volume_2.dat" udělá 2) a najde maximum
            ids = [int(f.split("_")[1].split(".")[0]) for f in existing_files]
            self.current_volume_id = max(ids)

        filepath = os.path.join(self.storage_dir, f"volume_{self.current_volume_id}.dat")

        # Otevřeme v režimu 'ab+' (append binary + čtení)
        self.file_handler = open(filepath, "ab+")
        # Zjistíme, kolik už tam toho je zapsáno (kdyby se server restartoval)
        self.current_size = os.path.getsize(filepath)
        print(f"📦 Inicializován svazek: {filepath} (Velikost: {self.current_size} B)")

    def _rotate_volume(self):
        """Zavře aktuální soubor a otevře nový s vyšším ID."""
        if self.file_handler:
            self.file_handler.close()

        self.current_volume_id += 1
        filepath = os.path.join(self.storage_dir, f"volume_{self.current_volume_id}.dat")
        self.file_handler = open(filepath, "ab+")
        self.current_size = 0
        print(f"🔄 Rotace svazku! Nový svazek: {filepath}")

    def append_data(self, data: bytes):
        """Zapíše data na konec souboru a vrátí metadata pro databázi."""
        with self.lock:
            data_size = len(data)

            # Kontrola, zda nepřekročíme limit. Pokud ano, točíme svazek!
            if self.current_size + data_size > self.max_size_bytes:
                self._rotate_volume()

            # Zjistíme přesný offset (pozici kurzoru), kam se bude zapisovat
            offset = self.file_handler.tell()

            # Samotný zápis
            self.file_handler.write(data)
            self.file_handler.flush()  # Vynutíme fyzický zápis z RAM na disk!

            self.current_size += data_size

            # Vracíme ty slavné 3 údaje, co si pamatuje Facebook
            return self.current_volume_id, offset, data_size

    def close(self):
        """Bezpečné zavření při vypínání serveru."""
        if self.file_handler:
            self.file_handler.close()

#kod pro testing
"""
if __name__ == "__main__":
    # Vytvoříme manažera s nesmyslně malým limitem (např. 50 bajtů),
    # abychom hned viděli, jak vytvoří druhý soubor.
    test_manager = HaystackManager(storage_dir="test_volumes", max_size_mb=0.00005)

    print("\n--- Test 1: Zápis prvních dat ---")
    vol1, off1, size1 = test_manager.append_data(b"Ahoj, toto je prvni fotka!")
    print(f"Zapsáno do volume {vol1}, offset: {off1}, size: {size1}")

    print("\n--- Test 2: Zápis dalších dat (přetečení) ---")
    vol2, off2, size2 = test_manager.append_data(
        b"Tohle uz by melo pretect do noveho volume, protoze je to moc dlouhe.")
    print(f"Zapsáno do volume {vol2}, offset: {off2}, size: {size2}")

    test_manager.close()
"""