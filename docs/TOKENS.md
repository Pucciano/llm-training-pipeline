> **Hinweis zum Lesen**
> *Alle Markdown-Pipes (`|`) in den Beispielen wurden mit `\|` maskiert, damit sie nicht als Spaltentrenner gewertet werden.
> `\`\`\`\` stellt drei Backticks dar, aber innerhalb eines Code-Spans.*

| Token                | Kategorie     | Zweck (Kurz)              | Beispiel (normal)       | Beispiel (im Dataset)     |
| -------------------- | ------------- | ------------------------- | ----------------------- | ------------------------- |
| `<s>`                | Basis         | Sequenz-Start             | —                       | `<s>`                     |
| `</s>`               | Basis         | Sequenz-Ende              | —                       | `</s>`                    |
| `<unk>`              | Basis         | Unknown/OOV               | —                       | `<unk>`                   |
| `<pad>`              | Basis         | Padding                   | —                       | `<pad>`                   |
| `<§>`                | Jur. Struktur | Paragraphenzeichen        | `§ 242 StGB`            | `<§> 242 StGB`            |
| `<Art.>`             | Jur. Struktur | Artikel-Präfix            | `Art. 14 GG`            | `<Art.> 14 GG`            |
| `<Abs.>`             | Jur. Struktur | Absatzangabe              | `Abs. 1`                | `<Abs.> 1`                |
| `<Satz>`             | Jur. Struktur | Satzangabe                | `Satz 2`                | `<Satz> 2`                |
| `<Nr.>`              | Jur. Struktur | Nummerangabe              | `Nr. 3`                 | `<Nr.> 3`                 |
| `<Rn.>`              | Jur. Struktur | Randnummer                | `Rn. 15`                | `<Rn.> 15`                |
| `<ECLI:>`            | Jur. Struktur | ECLI-Prefix               | `ECLI:DE:BGH:2025:1234` | `<ECLI:>DE:BGH:2025:1234` |
| `<AG>`               | Gericht       | Amtsgericht               | `AG München`            | `<AG> München`            |
| `<LG>`               | Gericht       | Landgericht               | `LG Berlin`             | `<LG> Berlin`             |
| `<OLG>`              | Gericht       | Oberlandesgericht         | `OLG Köln`              | `<OLG> Köln`              |
| `<BGH>`              | Gericht       | Bundesgerichtshof         | `BGH, Urteil v. …`      | `<BGH>, Urteil v. …`      |
| `<BVerfG>`           | Gericht       | Bundesverfassungsgericht  | `BVerfG, Beschl. …`     | `<BVerfG>, Beschl. …`     |
| `<BVerwG>`           | Gericht       | Bundesverwaltungsgericht  | `BVerwG 7 C 1/24`       | `<BVerwG> 7 C 1/24`       |
| `<BSG>`              | Gericht       | Bundessozialgericht       | `BSG B 12 KR …`         | `<BSG> B 12 KR …`         |
| `<BFH>`              | Gericht       | Bundesfinanzhof           | `BFH VI R …`            | `<BFH> VI R …`            |
| `<BAG>`              | Gericht       | Bundesarbeitsgericht      | `BAG 5 AZR …`           | `<BAG> 5 AZR …`           |
| `<FG>`               | Gericht       | Finanzgericht             | `FG Münster`            | `<FG> Münster`            |
| `<EuGH>`             | Gericht       | Gerichtshof der EU        | `EuGH C-123/24`         | `<EuGH> C-123/24`         |
| `<EuG>`              | Gericht       | Gericht (EU)              | `EuG T-99/23`           | `<EuG> T-99/23`           |
| `<GG>`               | Gesetz        | Grundgesetz               | `Art. 3 GG`             | `Art. 3 <GG>`             |
| `<BGB>`              | Gesetz        | Bürgerliches Gesetzbuch   | `§ 433 BGB`             | `<§> 433 <BGB>`           |
| `<HGB>`              | Gesetz        | Handelsgesetzbuch         | `§ 377 HGB`             | `<§> 377 <HGB>`           |
| `<StGB>`             | Gesetz        | Strafgesetzbuch           | `§ 242 StGB`            | `<§> 242 <StGB>`          |
| `<StPO>`             | Gesetz        | Strafprozessordnung       | `§ 136 StPO`            | `<§> 136 <StPO>`          |
| `<ZPO>`              | Gesetz        | Zivilprozessordnung       | `§ 511 ZPO`             | `<§> 511 <ZPO>`           |
| `<VwGO>`             | Gesetz        | VerwaltungsgerichtsO      | `§ 40 VwGO`             | `<§> 40 <VwGO>`           |
| `<VwVfG>`            | Gesetz        | VerwaltungsverfahrensG    | `§ 37 VwVfG`            | `<§> 37 <VwVfG>`          |
| `<AO>`               | Gesetz        | Abgabenordnung            | `§ 169 AO`              | `<§> 169 <AO>`            |
| `<SGB>`              | Gesetz        | Sozialgesetzbuch          | `§ 44 SGB X`            | `<§> 44 <SGB> X`          |
| `<IfSG>`             | Gesetz        | InfektionsschutzG         | `§ 34 IfSG`             | `<§> 34 <IfSG>`           |
| `<UStG>`             | Gesetz        | Umsatzsteuergesetz        | `§ 1 UStG`              | `<§> 1 <UStG>`            |
| `<EStG>`             | Gesetz        | Einkommensteuergesetz     | `§ 15 EStG`             | `<§> 15 <EStG>`           |
| `<GewO>`             | Gesetz        | Gewerbeordnung            | `§ 14 GewO`             | `<§> 14 <GewO>`           |
| `<UrhG>`             | Gesetz        | UrheberrechtsG            | `§ 32 UrhG`             | `<§> 32 <UrhG>`           |
| `<AktG>`             | Gesetz        | Aktiengesetz              | `§ 93 AktG`             | `<§> 93 <AktG>`           |
| `<InsO>`             | Gesetz        | Insolvenzordnung          | `§ 129 InsO`            | `<§> 129 <InsO>`          |
| `<GKG>`              | Gesetz        | Gerichtskostengesetz      | `§ 3 GKG`               | `<§> 3 <GKG>`             |
| `<GWB>`              | Gesetz        | GWB (Kartellrecht)        | `§ 1 GWB`               | `<§> 1 <GWB>`             |
| `<lex>`              | Latein        | „lex specialis“           | `lex specialis`         | `<lex> specialis`         |
| `<ratio>`            | Latein        | „ratio legis“             | `ratio legis`           | `<ratio> legis`           |
| `<subs>`             | Latein        | Subsumtion                | *subsumtieren*          | `<subs>umtiert`           |
| `<obiter>`           | Latein        | *obiter dictum*           | `obiter dictum`         | `<obiter> dictum`         |
| `<def>`              | Code-Py       | Funktionsdef.             | `def hello():`          | `<def> hello():`          |
| `<class>`            | Code-Py       | Klassendef.               | `class A:`              | `<class> A:`              |
| `<async>`            | Code-Py       | Async-Keyword             | `async def …`           | `<async> <def> …`         |
| `<await>`            | Code-Py       | Await-Keyword             | `await task`            | `<await> task`            |
| `<self>`             | Code-Py       | Instanz-Ref.              | `self.value`            | `<self>.value`            |
| `<#include>`         | Code-C        | Include                   | `#include <stdio.h>`    | `<#include> <stdio.h>`    |
| `<std::>`            | Code-C++      | Namespace-Präfix          | `std::cout`             | `<std::>cout`             |
| `<::>`               | Code-C++      | Scope-Operator            | `Class::func`           | `Class<::>func`           |
| `<->`                | Code-C++      | Pfeil-Operator            | `ptr->x`                | `ptr<->x`                 |
| `<fn>`               | Code-Rust     | Funktions-KW              | `fn main()`             | `<fn> main()`             |
| `<mut>`              | Code-Rust     | Mut-Modifier              | `let mut x`             | `let <mut> x`             |
| `<println!>`         | Code-Rust     | Print-Makro               | `println!("hi");`       | `<println!>("hi");`       |
| `<func>`             | Code-Go       | Funktions-KW              | `func main()`           | `<func> main()`           |
| `<package>`          | Code-Go       | Paket-Header              | `package main`          | `<package> main`          |
| `<chan>`             | Code-Go       | Kanal-Typ                 | `chan int`              | `<chan> int`              |
| `<go>`               | Code-Go       | Goroutine-Starter         | `go f()`                | `<go> f()`                |
| `<//>`               | Kommentar     | Einzeilig                 | `// note`               | `<//> note`               |
| `<#>`                | Kommentar     | Python-Kommentar          | `# todo`                | `<#> todo`                |
| `</*>`               | Kommentar     | Mehrzeiler-Start          | `/* text`               | `</*> text`               |
| `<*/>`               | Kommentar     | Mehrzeiler-Ende           | `text */`               | `text <*/>`               |
| `<MD_H1>`            | Markdown      | H1-Überschrift            | `# Titel`               | `<MD_H1> Titel`           |
| `<MD_H2>`            | Markdown      | H2-Überschrift            | `## Abschnitt`          | `<MD_H2> Abschnitt`       |
| `<MD_H3>`            | Markdown      | H3-Header                 | `### Punkt`             | `<MD_H3> Punkt`           |
| `<MD_H4>`            | Markdown      | H4-Header                 | `#### Detail`           | `<MD_H4> Detail`          |
| `<MD_UL>`            | Markdown      | Unsort. Liste             | `- Item`                | `<MD_UL> Item`            |
| `<MD_OL>`            | Markdown      | Nummernliste              | `1. Item`               | `<MD_OL> Item`            |
| `<MD_CB>`            | Markdown      | Code-Fence \`\`\`\`\`\`\` | `\`\`\`\`               | `<MD_CB>`                 |
| `<MD_CODE_LANG_py>`  | Markdown      | Fence python              | `\`\`\`python\`         | `<MD_CODE_LANG_py>`       |
| `<MD_CODE_LANG_cpp>` | Markdown      | Fence cpp                 | `\`\`\`cpp\`            | `<MD_CODE_LANG_cpp>`      |
| `<MD_CODE_LANG_rs>`  | Markdown      | Fence rust                | `\`\`\`rust\`           | `<MD_CODE_LANG_rs>`       |
| `<MD_CODE_LANG_go>`  | Markdown      | Fence go                  | `\`\`\`go\`             | `<MD_CODE_LANG_go>`       |
| `<MD_TABLE>`         | Markdown      | Tabellenstart             | `\|a\|b\|`              | `<MD_TABLE>`              |
| `<MD_END>`           | Markdown      | Block-Ende                | —                       | `<MD_END>`                |
