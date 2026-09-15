# Universal Academic Format Converter 🎓⚡

> Convert your academic manuscripts between journal, conference, publisher, and book templates (DOCX, LaTeX, LaTeX Project ZIP) seamlessly while preserving 100% scientific content integrity.

---

## 🌟 Overview & Vision

Manual manuscript reformatting between academic publishers (such as IEEE, Springer Nature, Elsevier, ACM) is tedious, time-consuming, and error-prone. 

Instead of relying on fragile $N \times M$ pairwise translators (e.g. `DOCX -> IEEE`, `LaTeX -> Springer`), **Universal Academic Format Converter** uses a unified **Universal Document Model (UDM)** compiler architecture:

```
SOURCE DOCUMENT / ZIP
          ↓
  SOURCE PARSER (DocxParser / LatexParser)
          ↓
UNIVERSAL DOCUMENT MODEL (UDM AST)
          ↓
DESTINATION TEMPLATE ANALYZER (Docx / Latex Spec)
          ↓
  MAPPING & INTEGRITY ENGINE
          ↓
DESTINATION RENDERER (DocxRenderer / LatexRenderer)
          ↓
VALIDATION & SANDBOX COMPILATION (PDF Preview & Zip Package)
```

---

## 🚀 Features

- **Compiler AST Architecture**: Parses manuscripts into a decoupled Universal Document Model preserving metadata, authors, affiliations, abstract, keywords, section hierarchies, math equations, tables, figures (with b64 images), and BibTeX reference entries.
- **LaTeX ZIP to LaTeX ZIP (First-Class)**: Preserves 100% of target template infrastructure (`.cls`, `.sty`, `.bst`, logos), translates metadata into target macro conventions (`\IEEEauthorblockN`, `\fnm`, `\sur`, `\affiliation`), places figure images, generates target `references.bib`, and packages output into `converted_project.zip`.
- **DOCX to LaTeX / DOCX to DOCX**: Compiles Word manuscripts directly into complete target LaTeX project ZIPs or publisher Word templates.
- **Content Integrity Assurance**: Performs normalized count comparison (Paragraphs, Figures, Tables, Equations, References) between source and output to guarantee zero content loss.
- **Template Conformity Validation**: Automated checklist validating page setup, margins, columns, typography, title block, author block, heading structure, and citation syntax.
- **Integrated PDF Preview**: Compiles instant PDF document previews via native TeX or integrated ReportLab UDM generator.
- **Modern Web Interface**: Responsive 2-column studio layout built with React, Vite, and FastAPI. Includes pre-loaded test packages and sample templates.

---

## 🛠️ Supported Workflows

| Workflow | Source Format | Target Format | Architecture |
|---|---|---|---|
| **Workflow A** | DOCX Manuscript | DOCX Template | `DOCX -> UDM -> DOCX` |
| **Workflow B** | DOCX Manuscript | LaTeX Project ZIP | `DOCX -> UDM -> LaTeX ZIP` |
| **Workflow C** | LaTeX Project ZIP (e.g. IEEE) | LaTeX Project ZIP (e.g. Springer) | `LaTeX ZIP -> UDM -> LaTeX ZIP` |
| **Workflow D** | LaTeX Project ZIP | DOCX Template | `LaTeX ZIP -> UDM -> DOCX` |
| **Workflow E** | LaTeX Project ZIP | Custom LaTeX Template | `LaTeX ZIP -> UDM -> Custom LaTeX` |

---

## 💻 Quickstart Guide

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/your-username/universal-academic-converter.git
cd universal-academic-converter

# Install Python dependencies
pip install fastapi uvicorn python-docx pylatexenc python-multipart pydantic jinja2 reportlab pillow

# Install Frontend dependencies and build bundle
cd frontend
npm install
npm run build
cd ..
```

### 2. Run the Application

Start the FastAPI backend server:

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open your browser to: **`http://127.0.0.1:8000`**

---

## 🧪 Testing & Verification

Run the integration test suite:

```bash
# Unit compiler test suite
python backend/test_server.py

# End-to-End API test (IEEE -> Springer LaTeX ZIP)
python backend/test_e2e_api.py

# DOCX -> Springer LaTeX ZIP workflow test
python backend/test_docx_to_latex.py
```

---

## 📄 Project Structure

```text
universal-academic-converter/
├── backend/
│   ├── app/
│   │   ├── models/         # UDM, TemplateSpecification, Report schemas
│   │   ├── parsers/        # DocxParser, LatexParser, ZipGuard
│   │   ├── template_engine/# TemplateAnalyzer
│   │   ├── mappers/        # MappingEngine
│   │   ├── renderers/      # DocxRenderer, LatexRenderer
│   │   ├── validation/     # IntegrityChecker, TemplateValidator
│   │   ├── compilation/    # LatexSandbox, PdfPreviewGenerator
│   │   └── main.py         # FastAPI App & Endpoints
│   └── samples/            # IEEE & Springer sample packages
├── frontend/               # React + TypeScript + Vite UI
│   └── src/
│       ├── components/     # Studio panels, Analysis cards, Report & Modal
│       ├── App.tsx
│       └── index.css
├── README.md
└── .gitignore
```

---

## ⚖️ License

MIT License. Designed for academic research and publication workflows.
