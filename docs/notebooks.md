# 📓 Interactive Jupyter Notebooks

This document provides guidance on using the Nelson-Siegel interactive Jupyter notebooks for yield curve analysis and education.

## 🎯 Available Notebooks

### 1. **Nelson_Siegel_Interactive_Analysis.ipynb** 
**Location**: `examples/Nelson_Siegel_Interactive_Analysis.ipynb`

**Description**: Comprehensive educational notebook covering yield curve analysis from fundamentals to advanced applications.

**Target Audience**: 
- Students learning fixed income analytics
- Practitioners new to Nelson-Siegel modeling
- Researchers exploring yield curve dynamics
- Portfolio managers seeking factor insights

**Prerequisites**:
- Basic understanding of bonds and interest rates
- Python programming knowledge (basic to intermediate)
- Familiarity with Jupyter notebooks

## 🚀 Getting Started

### Local Installation

1. **Install with interactive features**:
   ```bash
   pip install -e ".[interactive]"
   ```

2. **Launch the notebook**:
   ```bash
   jupyter lab examples/Nelson_Siegel_Interactive_Analysis.ipynb
   ```

3. **Enable widgets** (if not already enabled):
   ```bash
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyter-widgets/jupyterlab-manager
   ```

### Cloud Options

#### **Google Colab** (Recommended for beginners)
- Click the "Open in Colab" badge in the notebook
- No local installation required
- Free access to GPU resources

#### **Binder** (Full environment)
- Click the "Launch Binder" badge
- Complete environment setup
- May take a few minutes to load

#### **Azure Notebooks**
- Upload the notebook to Azure Notebooks
- Install requirements in the first cell

## 📚 Notebook Structure

### **Chapter Organization**

The interactive notebook is organized into educational chapters:

1. **🎓 Fundamentals**: Yield curve concepts and economic interpretation
2. **🔬 Model Theory**: Nelson-Siegel mathematical foundation
3. **🎛️ Interactive Exploration**: Real-time parameter manipulation
4. **💡 Economic Analysis**: Breakeven inflation and factor interpretation
5. **📈 Historical Analysis**: Factor evolution and market events
6. **💼 Applications**: Practical investment and risk management
7. **🎯 Advanced Strategies**: Portfolio optimization and factor trading
8. **🏁 Summary**: Key takeaways and next steps

### **Interactive Features**

Each chapter includes:
- **📊 Live visualizations** that update with parameter changes
- **🎛️ Interactive controls** (sliders, dropdowns, checkboxes)
- **💡 Economic interpretation** boxes explaining market implications
- **📈 Real data examples** with current market conditions
- **🔍 Deep-dive exercises** for hands-on learning

## 🛠️ Technical Requirements

### **Minimum Requirements**
- Python 3.8+
- 4GB RAM
- Modern web browser (Chrome, Firefox, Safari)
- Internet connection (for data downloads)

### **Recommended Setup**
- Python 3.10+
- 8GB RAM
- JupyterLab 3.0+
- FRED API key (for real market data)

### **Package Dependencies**
```python
# Core packages
numpy >= 1.21.0
pandas >= 1.3.0
scipy >= 1.7.0
matplotlib >= 3.4.0

# Interactive components
ipywidgets >= 7.6.0
jupyter >= 1.0.0
jupyterlab >= 3.0.0

# Optional data sources
fredapi >= 0.4.3  # FRED API access
yfinance >= 0.1.87  # Alternative data source
```

## 🎨 Customization Guide

### **Adding Your Own Data**

Replace synthetic data with real market data:

```python
# In the notebook, modify this section:
fred_api_key = "your_actual_api_key_here"  # Get from https://fred.stlouisfed.org/

# Or load from CSV files:
treasury_data = pd.read_csv('your_treasury_data.csv', index_col=0, parse_dates=True)
tips_data = pd.read_csv('your_tips_data.csv', index_col=0, parse_dates=True)
```

### **Modifying Parameter Ranges**

Adjust widget ranges for different markets:

```python
# Example: Modify for high-inflation environment
level_range = (0.0, 0.15)  # 0-15% instead of default 0-10%
slope_range = (-0.08, 0.08)  # Wider slope range
```

### **Adding New Analysis**

Extend the notebook with custom analysis:

```python
# Add new interactive section
def custom_analysis_widget():
    # Your custom analysis code here
    pass

# Create and display
custom_widget = widgets.interactive(custom_analysis_widget, ...)
display(custom_widget)
```

## 🔧 Troubleshooting

### **Common Issues**

1. **Widgets not displaying**:
   ```bash
   jupyter nbextension enable --py widgetsnbextension --sys-prefix
   jupyter labextension install @jupyter-widgets/jupyterlab-manager
   ```

2. **Import errors**:
   ```bash
   # Ensure package is installed in development mode
   pip install -e ".[interactive]"
   ```

3. **Slow performance**:
   - Reduce historical data range
   - Use subset of maturities
   - Close unused browser tabs

4. **Data download failures**:
   - Check internet connection
   - Verify FRED API key
   - Use synthetic data mode as fallback

### **Performance Optimization**

- **Reduce data size**: Use monthly instead of daily data
- **Limit date ranges**: Analyze shorter periods for faster processing
- **Use caching**: Save processed results for reuse
- **Close widgets**: Dispose of unused interactive elements

## 📖 Educational Use

### **For Instructors**

The notebook is designed for:
- **University courses** in fixed income or financial modeling
- **Professional training** programs
- **Self-study** curricula
- **Research workshops**

### **Learning Objectives**

After completing the notebook, users will:
- Understand yield curve economics and interpretation
- Master Nelson-Siegel parameter meanings and applications
- Analyze historical factor patterns and market events
- Apply factor insights to investment decisions
- Build custom yield curve analysis workflows

### **Assessment Ideas**

- Parameter interpretation exercises
- Historical event analysis projects
- Custom scenario construction
- Portfolio optimization challenges

## 🤝 Contributing

### **Adding New Content**

1. Follow the established chapter structure
2. Include both educational and interactive elements
3. Provide economic context for all analyses
4. Test with both synthetic and real data

### **Improving Interactivity**

1. Use consistent widget styling
2. Include parameter validation
3. Provide helpful error messages
4. Add progress indicators for long operations

### **Documentation**

1. Update this guide for new features
2. Include screenshots for complex procedures
3. Provide troubleshooting solutions
4. Maintain version compatibility notes

## 📞 Support

For notebook-specific issues:
- **GitHub Issues**: [Repository Issues](https://github.com/alanvaa06/nelson-siegel/issues)
- **Documentation**: [Project Documentation](https://nelson-siegel.readthedocs.io/)
- **Email**: research@example.com

For Jupyter/widget issues:
- **Jupyter Documentation**: [jupyter.org](https://jupyter.org/documentation)
- **ipywidgets Documentation**: [ipywidgets.readthedocs.io](https://ipywidgets.readthedocs.io/)
