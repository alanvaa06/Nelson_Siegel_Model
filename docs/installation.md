# 🚀 Installation Guide

This guide provides detailed installation instructions for the Nelson-Siegel yield curve analysis library with special attention to interactive notebook functionality.

## 📋 Installation Options

### 1. **Basic Installation** (Core Functionality)

For command-line usage and Python scripts:

```bash
pip install -e .
```

**What you get**:
- Core Nelson-Siegel modeling
- Data download capabilities
- Static plotting and analysis
- Command-line interface

### 2. **Interactive Installation** (Recommended)

For Jupyter notebook with interactive widgets:

```bash
pip install -e ".[interactive]"
```

**What you get**:
- Everything from basic installation
- Interactive Jupyter widgets
- Real-time parameter exploration
- Educational notebook features

### 3. **Development Installation** (Contributors)

For development and testing:

```bash
pip install -e ".[dev]"
```

**What you get**:
- Everything from basic installation
- Testing framework (pytest)
- Code quality tools (black, mypy, flake8)
- Pre-commit hooks

### 4. **Complete Installation** (Everything)

For full functionality including data sources:

```bash
pip install -e ".[dev,interactive,data,notebooks]"
```

**What you get**:
- All features and dependencies
- Multiple data source options
- Complete development environment
- Optimized notebook experience

## 🔧 System Requirements

### **Minimum Requirements**
- Python 3.8 or higher
- 4GB RAM
- 1GB free disk space
- Internet connection (for data downloads)

### **Recommended Specifications**
- Python 3.10 or higher
- 8GB RAM
- Modern multi-core processor
- SSD storage
- Stable internet connection

## 📓 Jupyter Notebook Setup

### **Step 1: Install with Interactive Features**

```bash
pip install -e ".[interactive]"
```

### **Step 2: Enable Widget Extensions**

For **Jupyter Lab** (Recommended):
```bash
# Install widget extension
jupyter labextension install @jupyter-widgets/jupyterlab-manager

# Rebuild lab
jupyter lab build
```

For **Classic Jupyter Notebook**:
```bash
# Enable widgets
jupyter nbextension enable --py widgetsnbextension --sys-prefix
```

### **Step 3: Verify Installation**

Test that everything works:

```python
# In a Jupyter cell, run:
import nelson_siegel
from nelson_siegel.interactive import InteractiveYieldCurveExplorer
print("✅ Installation successful!")
```

## 🌐 Cloud Installation Options

### **Google Colab** (Zero Installation)

1. Click the "Open in Colab" badge in the notebook
2. Run the first cell to install dependencies:
   ```python
   !pip install git+https://github.com/alanvaa06/nelson-siegel.git[interactive]
   ```

### **Binder** (Pre-configured Environment)

1. Click the "Launch Binder" badge
2. Wait for environment to build (2-3 minutes)
3. Open the notebook and start exploring

### **Azure Notebooks**

1. Upload the repository to Azure Notebooks
2. Create a new compute instance
3. Install dependencies in the first cell

## 🔑 API Key Setup (Optional)

For real market data access, get a free FRED API key:

### **Step 1: Register for FRED API**
1. Visit [https://fred.stlouisfed.org/](https://fred.stlouisfed.org/)
2. Create a free account
3. Request an API key (instant approval)

### **Step 2: Configure API Key**

**Option A: Environment Variable** (Recommended)
```bash
export FRED_API_KEY="your_api_key_here"
```

**Option B: Direct Configuration**
```python
# In your Python code or notebook:
fred_api_key = "your_api_key_here"
analyzer = YieldCurveAnalyzer(fred_api_key=fred_api_key)
```

**Option C: Configuration File**
```python
# Create config.py file:
FRED_API_KEY = "your_api_key_here"

# Import in your code:
from config import FRED_API_KEY
```

## 🔧 Troubleshooting

### **Common Installation Issues**

#### **Problem**: `pip install` fails with permission errors
**Solution**:
```bash
# Use user installation
pip install --user -e ".[interactive]"

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[interactive]"
```

#### **Problem**: Widget extensions not working
**Solution**:
```bash
# For JupyterLab
jupyter labextension list  # Check installed extensions
jupyter labextension install @jupyter-widgets/jupyterlab-manager --no-build
jupyter lab build

# For Classic Notebook
jupyter nbextension list  # Check enabled extensions
jupyter nbextension enable --py widgetsnbextension --sys-prefix
```

#### **Problem**: Import errors in notebook
**Solution**:
```python
# Add to first notebook cell:
import sys
from pathlib import Path
src_path = Path.cwd().parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))
```

#### **Problem**: Slow performance in notebooks
**Solution**:
- Reduce historical data range
- Use monthly instead of daily data
- Close unused browser tabs
- Restart Jupyter kernel periodically

### **Version Compatibility**

| Component | Minimum Version | Recommended |
|-----------|-----------------|-------------|
| Python | 3.8 | 3.10+ |
| NumPy | 1.21.0 | Latest |
| Pandas | 1.3.0 | Latest |
| Jupyter | 1.0.0 | Latest |
| JupyterLab | 3.0.0 | 3.4+ |
| ipywidgets | 7.6.0 | 8.0+ |

### **Package Conflicts**

If you encounter package conflicts:

```bash
# Create clean environment
conda create -n nelson-siegel python=3.10
conda activate nelson-siegel
pip install -e ".[interactive]"
```

## 🚀 Quick Verification

After installation, verify everything works:

### **1. Test Basic Functionality**
```python
from nelson_siegel import TreasuryNelsonSiegelModel
import numpy as np

# Create test data
maturities = np.array([1, 2, 5, 10, 30])
yields = np.array([0.02, 0.025, 0.03, 0.032, 0.035])

# Fit model
model = TreasuryNelsonSiegelModel()
model.fit(maturities, yields)
print("✅ Basic functionality working")
```

### **2. Test Interactive Features**
```python
from nelson_siegel.interactive import InteractiveYieldCurveExplorer
explorer = InteractiveYieldCurveExplorer('treasury')
print("✅ Interactive features available")
```

### **3. Test Data Download**
```python
from nelson_siegel import DataManager
dm = DataManager()
data = dm.get_treasury_data()
print(f"✅ Data download working: {len(data)} days of data")
```

## 📚 Next Steps

After successful installation:

1. **📓 Start with the Interactive Notebook**:
   ```bash
   jupyter lab examples/Nelson_Siegel_Interactive_Analysis.ipynb
   ```

2. **🐍 Explore Python Examples**:
   ```bash
   python examples/basic_usage.py
   ```

3. **🤖 Try Command Line Interface**:
   ```bash
   python scripts/run_analysis.py treasury --days 30
   ```

4. **📖 Read the Documentation**:
   - [Notebook Guide](notebooks.md)
   - [API Reference](api.md)
   - [User Guide](user_guide.md)

## 🆘 Getting Help

If you encounter issues:

1. **Check the troubleshooting section** above
2. **Search existing issues** on GitHub
3. **Create a new issue** with detailed error information
4. **Join the discussion** on GitHub Discussions

**When reporting issues, please include**:
- Operating system and version
- Python version
- Complete error message
- Steps to reproduce the problem
