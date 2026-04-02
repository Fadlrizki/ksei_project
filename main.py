import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import glob
import os
from datetime import datetime
import pickle

# Page config
st.set_page_config(
    page_title="KSEI Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 20px;
        padding: 1rem;
        border: 1px solid rgba(255,255,255,0.1);
        transition: transform 0.3s ease;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #94a3b8;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: white;
        margin-top: 0.3rem;
    }
    .metric-delta {
        font-size: 0.75rem;
        margin-top: 0.3rem;
    }
    .delta-positive { color: #10b981; }
    .delta-negative { color: #ef4444; }
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        margin: 1rem 0 0.8rem 0;
        padding-left: 0.5rem;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# ==================== FUNCTIONS ====================

@st.cache_data(ttl=3600, show_spinner=False)
def load_cleaned_data(filepath):
    """Load data yang sudah dibersihkan (sudah melalui proses cleaning sebelumnya)"""
    df = pd.read_csv(filepath)
    
    # Pastikan kolom yang diperlukan ada
    required_cols = ['SHARE_CODE', 'ISSUER_NAME_CLEAN', 'INVESTOR_NAME_CLEAN', 
                     'PERCENTAGE', 'TOTAL_HOLDING_SHARES', 'INVESTOR_TYPE', 
                     'LOCAL_FOREIGN', 'DATE']
    
    # Jika kolom cleaned tidak ada, gunakan kolom asli
    if 'ISSUER_NAME_CLEAN' not in df.columns:
        df['ISSUER_NAME_CLEAN'] = df['ISSUER_NAME']
    if 'INVESTOR_NAME_CLEAN' not in df.columns:
        df['INVESTOR_NAME_CLEAN'] = df['INVESTOR_NAME']
    
    # Parse date jika perlu
    if 'DATE' in df.columns and df['DATE'].dtype == 'object':
        df['DATE'] = pd.to_datetime(df['DATE'], errors='coerce')
    
    # Get date from filename if SOURCE_DATE_STR not exists
    if 'SOURCE_DATE_STR' not in df.columns:
        date_str = Path(filepath).stem
        try:
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            df['SOURCE_DATE_STR'] = file_date.strftime('%d %b %Y')
        except:
            df['SOURCE_DATE_STR'] = date_str
    
    return df

def get_file_info(data_dir="data"):
    """Get all CSV files with their dates"""
    data_path = Path(data_dir)
    data_path.mkdir(exist_ok=True)
    
    csv_files = []
    for file in data_path.glob("*.csv"):
        # Skip cleaned files to avoid duplicates (optional)
        # if '_cleaned' in file.name:
        #     continue
            
        try:
            date_str = file.stem[:10]  # Take YYYY-MM-DD part
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            file_date = datetime.fromtimestamp(file.stat().st_mtime)
        
        csv_files.append({
            'path': str(file),
            'filename': file.name,
            'date': file_date,
            'date_str': file_date.strftime('%d %b %Y')
        })
    
    csv_files.sort(key=lambda x: x['date'], reverse=True)
    return csv_files

def get_changes(df_old, df_new):
    """Get new and lost investors between two periods"""
    if df_old is None or df_new is None or df_old.empty or df_new.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Use cleaned names for matching
    old_keys = set(df_old['SHARE_CODE'] + '|' + df_old['INVESTOR_NAME_CLEAN'])
    new_keys = set(df_new['SHARE_CODE'] + '|' + df_new['INVESTOR_NAME_CLEAN'])
    
    # New entries
    new_keys_list = list(new_keys - old_keys)
    new_entries = []
    if new_keys_list:
        for key in new_keys_list[:100]:  # Limit for performance
            code, name = key.split('|', 1)
            row = df_new[(df_new['SHARE_CODE'] == code) & 
                         (df_new['INVESTOR_NAME_CLEAN'] == name)]
            if not row.empty:
                row = row.iloc[0]
                new_entries.append({
                    'INVESTOR_NAME': row['INVESTOR_NAME_CLEAN'],
                    'SHARE_CODE': row['SHARE_CODE'],
                    'ISSUER_NAME': row['ISSUER_NAME_CLEAN'],
                    'PERCENTAGE': row['PERCENTAGE'],
                    'SHARES_M': row['TOTAL_HOLDING_SHARES'] / 1e6
                })
    
    # Lost entries
    lost_keys_list = list(old_keys - new_keys)
    lost_entries = []
    if lost_keys_list:
        for key in lost_keys_list[:100]:
            code, name = key.split('|', 1)
            row = df_old[(df_old['SHARE_CODE'] == code) & 
                         (df_old['INVESTOR_NAME_CLEAN'] == name)]
            if not row.empty:
                row = row.iloc[0]
                lost_entries.append({
                    'INVESTOR_NAME': row['INVESTOR_NAME_CLEAN'],
                    'SHARE_CODE': row['SHARE_CODE'],
                    'ISSUER_NAME': row['ISSUER_NAME_CLEAN'],
                    'PERCENTAGE': row['PERCENTAGE'],
                    'SHARES_M': row['TOTAL_HOLDING_SHARES'] / 1e6
                })
    
    return (pd.DataFrame(new_entries) if new_entries else pd.DataFrame(),
            pd.DataFrame(lost_entries) if lost_entries else pd.DataFrame())

# ==================== LOAD DATA ====================

# Get files
files_info = get_file_info()

if len(files_info) < 1:
    st.error("Tidak ada file CSV di folder 'data/'")
    st.info("""
    **Cara penggunaan:**
    1. Simpan file CSV hasil cleaning ke folder `data/`
    2. Format nama file: `YYYY-MM-DD.csv` (contoh: `2026-04-02.csv`)
    3. Pastikan file sudah memiliki kolom:
       - `INVESTOR_NAME_CLEAN` dan `ISSUER_NAME_CLEAN` (hasil cleaning)
       - Atau kolom asli `INVESTOR_NAME` dan `ISSUER_NAME`
    """)
    st.stop()

# Load latest data
with st.spinner("Memuat data..."):
    latest_file = files_info[0]
    df_latest = load_cleaned_data(latest_file['path'])
    latest_date = df_latest['SOURCE_DATE_STR'].iloc[0] if not df_latest.empty else latest_file['date_str']
    
    # Load previous if exists
    df_previous = None
    prev_date = None
    if len(files_info) >= 2:
        prev_file = files_info[1]
        df_previous = load_cleaned_data(prev_file['path'])
        prev_date = df_previous['SOURCE_DATE_STR'].iloc[0] if not df_previous.empty else prev_file['date_str']
    
    # Get changes
    new_investors, lost_investors = get_changes(df_previous, df_latest)

# Calculate metrics
total_shares = df_latest['TOTAL_HOLDING_SHARES'].sum() / 1e9
prev_total_shares = df_previous['TOTAL_HOLDING_SHARES'].sum() / 1e9 if df_previous is not None else total_shares
shares_change = total_shares - prev_total_shares

# ==================== DASHBOARD ====================

st.markdown('<p class="main-header">📊 KSEI Analytics Dashboard</p>', unsafe_allow_html=True)
st.caption(f"Data: {latest_date}" + (f" (vs {prev_date})" if prev_date else ""))

# Metrics Row
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🏢 Total Perusahaan</div>
        <div class="metric-value">{df_latest['SHARE_CODE'].nunique():,}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">👥 Total Investor</div>
        <div class="metric-value">{df_latest['INVESTOR_NAME_CLEAN'].nunique():,}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">📊 Rata-rata</div>
        <div class="metric-value">{df_latest['PERCENTAGE'].mean():.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    delta_class = "delta-positive" if shares_change >= 0 else "delta-negative"
    delta_symbol = "▲" if shares_change >= 0 else "▼"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">💰 Total Saham</div>
        <div class="metric-value">{total_shares:.1f}B</div>
        <div class="metric-delta {delta_class}">{delta_symbol} {abs(shares_change):.1f}B</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    new_count = len(new_investors)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🆕 Investor Baru</div>
        <div class="metric-value">{new_count}</div>
    </div>
    """, unsafe_allow_html=True)

# New Investors Section
if not new_investors.empty:
    st.markdown('<div class="section-header">🆕 Investor / Perusahaan Baru</div>', unsafe_allow_html=True)
    
    new_display = new_investors.nlargest(8, 'SHARES_M')[['INVESTOR_NAME', 'SHARE_CODE', 'ISSUER_NAME', 'PERCENTAGE', 'SHARES_M']]
    new_display['SHARES_M'] = new_display['SHARES_M'].round(0).astype(int)
    
    col1, col2 = st.columns([1.5, 1])
    with col1:
        st.dataframe(
            new_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                'PERCENTAGE': st.column_config.NumberColumn(format="%.2f%%"),
                'SHARES_M': st.column_config.NumberColumn(label="Saham (Juta)", format="%d")
            }
        )
    with col2:
        fig = px.bar(
            new_display.head(8),
            x='INVESTOR_NAME',
            y='SHARES_M',
            title="Top 8 Investor Baru",
            color='PERCENTAGE',
            color_continuous_scale='Greens'
        )
        fig.update_layout(xaxis_tickangle=-45, height=320)
        st.plotly_chart(fig, use_container_width=True)

# Top Rankings
st.markdown('<div class="section-header">🏆 Top Rankings</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📈 Top Saham", "👑 Top Investor", "🏢 Top Perusahaan"])

with tab1:
    top_stocks = df_latest.groupby(['SHARE_CODE', 'ISSUER_NAME_CLEAN']).agg({
        'TOTAL_HOLDING_SHARES': 'sum',
        'PERCENTAGE': 'sum'
    }).round(2).sort_values('TOTAL_HOLDING_SHARES', ascending=False).head(10).reset_index()
    top_stocks['SHARES_M'] = (top_stocks['TOTAL_HOLDING_SHARES'] / 1e6).round(0).astype(int)
    
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.dataframe(
            top_stocks[['SHARE_CODE', 'ISSUER_NAME_CLEAN', 'SHARES_M', 'PERCENTAGE']],
            use_container_width=True,
            hide_index=True,
            column_config={'PERCENTAGE': st.column_config.NumberColumn(format="%.2f%%")}
        )
    with col2:
        fig = px.bar(top_stocks, x='SHARE_CODE', y='TOTAL_HOLDING_SHARES', 
                     title="Top 10 Saham", color='PERCENTAGE', color_continuous_scale='Blues',
                     text='SHARES_M')
        fig.update_traces(textposition='outside')
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    top_investors = df_latest.groupby(['INVESTOR_NAME_CLEAN', 'INVESTOR_TYPE']).agg({
        'TOTAL_HOLDING_SHARES': 'sum',
        'PERCENTAGE': 'sum',
        'SHARE_CODE': 'count'
    }).round(2).sort_values('TOTAL_HOLDING_SHARES', ascending=False).head(10).reset_index()
    top_investors['SHARES_M'] = (top_investors['TOTAL_HOLDING_SHARES'] / 1e6).round(0).astype(int)
    top_investors.columns = ['INVESTOR_NAME', 'TYPE', 'TOTAL_SHARES', 'TOTAL_PCT', 'COMPANY_COUNT', 'SHARES_M']
    
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.dataframe(
            top_investors[['INVESTOR_NAME', 'SHARES_M', 'TOTAL_PCT', 'COMPANY_COUNT', 'TYPE']],
            use_container_width=True,
            hide_index=True,
            column_config={'TOTAL_PCT': st.column_config.NumberColumn(format="%.2f%%")}
        )
    with col2:
        fig = px.bar(top_investors, x='INVESTOR_NAME', y='TOTAL_SHARES',
                     title="Top 10 Investor", color='TOTAL_PCT', color_continuous_scale='Viridis',
                     text='SHARES_M')
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_tickangle=-45, height=380)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    top_companies = df_latest.groupby(['SHARE_CODE', 'ISSUER_NAME_CLEAN']).agg({
        'TOTAL_HOLDING_SHARES': 'sum',
        'PERCENTAGE': 'sum',
        'INVESTOR_NAME_CLEAN': 'count'
    }).round(2).sort_values('TOTAL_HOLDING_SHARES', ascending=False).head(10).reset_index()
    top_companies['SHARES_M'] = (top_companies['TOTAL_HOLDING_SHARES'] / 1e6).round(0).astype(int)
    top_companies.columns = ['SHARE_CODE', 'ISSUER_NAME', 'TOTAL_SHARES', 'TOTAL_PCT', 'INVESTOR_COUNT', 'SHARES_M']
    
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.dataframe(
            top_companies[['SHARE_CODE', 'ISSUER_NAME', 'SHARES_M', 'TOTAL_PCT', 'INVESTOR_COUNT']],
            use_container_width=True,
            hide_index=True,
            column_config={'TOTAL_PCT': st.column_config.NumberColumn(format="%.2f%%")}
        )
    with col2:
        fig = px.bar(top_companies, x='SHARE_CODE', y='TOTAL_SHARES',
                     title="Top 10 Perusahaan", color='TOTAL_PCT', color_continuous_scale='Oranges',
                     text='SHARES_M')
        fig.update_traces(textposition='outside')
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

# Company Detail
st.markdown('<div class="section-header">🔍 Detail Perusahaan</div>', unsafe_allow_html=True)

companies = sorted(df_latest['SHARE_CODE'].unique())
selected_company = st.selectbox("Pilih Perusahaan:", companies, key="company_select")

if selected_company:
    company_data = df_latest[df_latest['SHARE_CODE'] == selected_company].copy()
    company_name = company_data['ISSUER_NAME_CLEAN'].iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👥 Investor", len(company_data))
    with col2:
        st.metric("📊 Total", f"{company_data['PERCENTAGE'].sum():.2f}%")
    with col3:
        st.metric("🏆 Terbesar", f"{company_data['PERCENTAGE'].max():.2f}%")
    with col4:
        st.metric("💰 Saham", f"{company_data['TOTAL_HOLDING_SHARES'].sum() / 1e6:.1f}Jt")
    
    # Show changes for this company
    if df_previous is not None:
        prev_company = df_previous[df_previous['SHARE_CODE'] == selected_company]
        if not prev_company.empty:
            prev_investors = set(prev_company['INVESTOR_NAME_CLEAN'])
            curr_investors = set(company_data['INVESTOR_NAME_CLEAN'])
            
            col1, col2 = st.columns(2)
            with col1:
                new_inv = curr_investors - prev_investors
                if new_inv:
                    st.markdown("**🆕 Investor Baru:**")
                    for inv in list(new_inv)[:5]:
                        inv_data = company_data[company_data['INVESTOR_NAME_CLEAN'] == inv].iloc[0]
                        st.info(f"📈 {inv} - {inv_data['PERCENTAGE']:.2f}%")
            with col2:
                lost_inv = prev_investors - curr_investors
                if lost_inv:
                    st.markdown("**❌ Investor Keluar:**")
                    for inv in list(lost_inv)[:5]:
                        inv_data = prev_company[prev_company['INVESTOR_NAME_CLEAN'] == inv].iloc[0]
                        st.warning(f"📉 {inv} - {inv_data['PERCENTAGE']:.2f}%")
    
    # Investor list
    st.dataframe(
        company_data[['INVESTOR_NAME_CLEAN', 'PERCENTAGE', 'TOTAL_HOLDING_SHARES', 'INVESTOR_TYPE']]
        .sort_values('PERCENTAGE', ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            'PERCENTAGE': st.column_config.NumberColumn(format="%.2f%%"),
            'TOTAL_HOLDING_SHARES': st.column_config.NumberColumn(format="%d")
        }
    )
    
    fig = px.bar(company_data.head(15), x='INVESTOR_NAME_CLEAN', y='PERCENTAGE',
                 title=f"Top Investor di {selected_company}", color='PERCENTAGE',
                 color_continuous_scale='Viridis', text='PERCENTAGE')
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(xaxis_tickangle=-45, height=400)
    st.plotly_chart(fig, use_container_width=True)

# Investor Detail
st.markdown('<div class="section-header">🔍 Detail Investor</div>', unsafe_allow_html=True)

investors = sorted(df_latest['INVESTOR_NAME_CLEAN'].unique())
selected_investor = st.selectbox("Pilih Investor:", investors, key="investor_select")

if selected_investor:
    investor_data = df_latest[df_latest['INVESTOR_NAME_CLEAN'] == selected_investor].copy()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏢 Perusahaan", len(investor_data))
    with col2:
        st.metric("📊 Total", f"{investor_data['PERCENTAGE'].sum():.2f}%")
    with col3:
        st.metric("💰 Saham", f"{investor_data['TOTAL_HOLDING_SHARES'].sum() / 1e6:.1f}Jt")
    with col4:
        tipe = investor_data['INVESTOR_TYPE'].iloc[0] if not investor_data.empty else '-'
        st.metric("🏷️ Tipe", tipe)
    
    # Show changes for this investor
    if df_previous is not None:
        prev_investor = df_previous[df_previous['INVESTOR_NAME_CLEAN'] == selected_investor]
        if not prev_investor.empty:
            prev_stocks = set(prev_investor['SHARE_CODE'])
            curr_stocks = set(investor_data['SHARE_CODE'])
            
            col1, col2 = st.columns(2)
            with col1:
                new_stocks = curr_stocks - prev_stocks
                if new_stocks:
                    st.markdown("**🆕 Saham Baru:**")
                    for code in list(new_stocks)[:5]:
                        stock_data = investor_data[investor_data['SHARE_CODE'] == code].iloc[0]
                        st.info(f"📈 {code} - {stock_data['PERCENTAGE']:.2f}%")
            with col2:
                lost_stocks = prev_stocks - curr_stocks
                if lost_stocks:
                    st.markdown("**❌ Saham Keluar:**")
                    for code in list(lost_stocks)[:5]:
                        stock_data = prev_investor[prev_investor['SHARE_CODE'] == code].iloc[0]
                        st.warning(f"📉 {code} - {stock_data['PERCENTAGE']:.2f}%")
    
    # Portfolio
    st.dataframe(
        investor_data[['SHARE_CODE', 'ISSUER_NAME_CLEAN', 'PERCENTAGE', 'TOTAL_HOLDING_SHARES']]
        .sort_values('PERCENTAGE', ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            'PERCENTAGE': st.column_config.NumberColumn(format="%.2f%%"),
            'TOTAL_HOLDING_SHARES': st.column_config.NumberColumn(format="%d")
        }
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if len(investor_data) > 1:
            fig = px.pie(investor_data, values='PERCENTAGE', names='SHARE_CODE', 
                         title=f"Distribusi Portfolio")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(investor_data, x='SHARE_CODE', y='PERCENTAGE',
                     title=f"Kepemilikan per Saham", color='PERCENTAGE',
                     color_continuous_scale='Viridis', text='PERCENTAGE')
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

# Footer
st.divider()
st.caption(f"📊 KSEI Analytics Dashboard | 📅 {latest_date}" + (f" (vs {prev_date})" if prev_date else "") + " | 🎯 Kepemilikan >1%")