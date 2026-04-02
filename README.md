SmartSurat: Invictus Edition
"Segalanya Lebih Cekap" — A secure, local-first digital letter management and tracking system for JKR 2026.

SmartSurat is a high-performance Streamlit application designed to eliminate "lost letters" and manual data entry errors. By leveraging Local OCR and a persistent JSON database, it provides a seamless end-to-end workflow from initial upload to department-level confirmation.

🚀 Key Features
🔐 1. Multi-Role Access Control (RBAC)
The system is divided into four distinct professional roles to ensure data integrity and security:

User (Staff): Digitalize incoming physical mail and track personal upload status.

Admin (Clerk): Automated data extraction using Tesseract OCR with manual verification.

Wakil Penerima (Dept Rep): Exclusive inbox for department-specific letter acknowledgment.

Senior Admin (Management): Real-time analytics dashboard and professional Excel reporting.

🧠 2. Intelligent Automation
Smart OCR: Automatically extracts Nombor Rujukan, Tarikh Surat, and Perkara from JKR documents.

Instant Persistence: Uses a shared data_log.json database, allowing multiple users to see updates across different tabs/browsers in real-time.

🛡️ 3. Privacy & Security
100% Local Processing: No external API calls. Your data never leaves the JKR network.

Atomic Writes: Uses a temporary-file-swap system to prevent data corruption during simultaneous access.

🛠️ System Architecture
The workflow ensures that every letter is tracked through its entire lifecycle:
Upload (Baru) → Verified (Diminitkan) → Acknowledge (Diterima).

💻 Installation & Local Setup
Prerequisites
Python 3.9+

Tesseract OCR Engine installed at C:\Program Files\Tesseract-OCR
