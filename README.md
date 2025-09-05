# 🚀 Advanced File Copy Utility (SmartCopy Utility)

An advanced Python-based file copy utility with **progress bars, checksum verification, retries, and system stats** (CPU, RAM, network speed). Perfect for reliable file transfers with visual feedback.  

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg" alt="Platform" />
</p>

---

## 🔧 Installation  

### 1. Clone the repository  
```bash
https://github.com/im-jayson-f/Advanced-File-Copy-Utility.git
```

### 2. Create and activate a virtual environment *(optional but recommended)*  
```bash
python -m venv venv
# On Linux/macOS
source venv/bin/activate
# On Windows
venv\Scripts\activate
```

### 3. Install dependencies  
install manually:  
```bash
pip install tqdm colorama psutil
```

---

## ▶️ Usage  

Basic command:  
```bash
python SmartCopy-Utility.py <source> <destination> [--retry N]
```

### 💡 Examples  
Copy a folder from C: to D:  
```bash
python SmartCopy-Utility.py "C:\source_folder" "D:\destination_folder"
```

Copy a file with 3 retry attempts on failure:  
```bash
python SmartCopy-Utility.py "./my file.zip" "./backup" --retry 3
```

---

## ⚙️ Arguments  

| Argument        | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `source`        | ✅ Yes   | –       | Path of the file or folder to copy. |
| `destination`   | ✅ Yes   | –       | Path to the destination folder. |
| `--retry N`     | ❌ No    | `0`     | Number of retries for failed file copies. `0` = no retry (only one attempt). |

---

## ✨ Features  

- 📊 **Progress bar** with file size tracking  
- 🔒 **Checksum verification** to ensure data integrity  
- 🔁 **Retry mechanism** for failed copies  
- 🖥️ **System stats** (CPU, RAM, network speed) displayed in real time  
- 🌍 **Cross-platform support** (Windows, macOS, Linux)  

---

## 📦 Requirements  

The following Python packages are required:  
- `tqdm`  
- `colorama`  
- `psutil`  

Install them via:  
```bash
pip install tqdm colorama psutil
```

---

## 📸 Demo Output  

```
--- Advanced Python File Copy Utility ---

Source:      C:\source_folder
Destination: D:\destination_folder
Retries:     3

100% |██████████████████████████████████████████████████████████████| 12.3G/12.3G [6:46:27<7:19:19, 1.82MB/s]
CPU:  12.5% | RAM:  48.3% | Up:  0.00 KB/s | Down:  0.00 KB/s | File: example.bak

✔️ Transfer complete!
Total time elapsed: 53 second(s)

Press Enter to exit.
```

---

## 📜 License  

MIT License. Free to use and modify 😊✨  
