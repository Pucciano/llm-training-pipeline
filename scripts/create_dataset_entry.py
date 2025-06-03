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

            entry = {
                "instruction": instruction,
                "input": input_text,
                "output": output,
                "meta": {
                    "created_at": datetime.utcnow().isoformat() + "Z"
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
