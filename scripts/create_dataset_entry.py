import json
from datetime import datetime
from pathlib import Path

DATASET_PATH = Path("../data/dataset.jsonl")


def ask_input(prompt: str, multiline: bool = False) -> str:
    """
    Fragt Benutzereingaben ab. Unterstützt optional mehrzeilige Eingaben.
    """
    print(prompt)
    if multiline:
        print("(Mehrzeilige Eingabe: Mit leerer Zeile beenden)")
        lines = []
        while True:
            line = input()
            if line.strip() == "":
                break
            lines.append(line)
        return "\n".join(lines).strip()
    else:
        return input("> ").strip()


def main():
    print("🧠 Interaktive Eingabe für Instruction-Tuning-Dataset")
    print("Drücke STRG+C oder lasse 'instruction' leer zum Beenden.\n")

    while True:
        try:
            instruction = ask_input("📌 Instruction (Was soll das Modell tun?)")
            if not instruction:
                print("Beendet.")
                break

            input_text = ask_input("📥 Input (optional, Kontext o. Aufgabe)", multiline=True)
            output = ask_input("📝 Output (Antwort des Modells)", multiline=True)

            if not output:
                print("⚠️ Warnung: Output ist leer. Eingabe wird übersprungen.\n")
                continue

            tags_input = ask_input("🏷️ Themen-Tags (z.B. 'forensik, python, grammatik')")
            tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]

            source = ask_input("📚 Quelle der Daten (z.B. 'OpenBook: Deutsch A1 – Lektion 3')")
            license_info = ask_input("📄 Lizenz (z.B. 'CC-BY-SA 4.0', 'privat', 'Alle Rechte vorbehalten')")

            entry = {
                "instruction": instruction,
                "input": input_text,
                "output": output,
                "meta": {
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "tags": tags,
                    "source": source,
                    "license": license_info
                }
            }

            with open(DATASET_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            print(f"✅ Eintrag gespeichert ({DATASET_PATH.name})\n")

        except KeyboardInterrupt:
            print("\n⛔ Abbruch durch Benutzer. Auf Wiedersehen.")
            break
        except Exception as e:
            print(f"❌ Fehler: {e}")


if __name__ == "__main__":
    main()
