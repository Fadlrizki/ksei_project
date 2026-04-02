import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import glob
import os
from datetime import datetime

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
    .metric-card:hover {
        transform: translateY(-5px);
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
    .sub-section-header {
        font-size: 1rem;
        font-weight: 600;
        margin: 0.8rem 0 0.5rem 0;
        color: #475569;
    }
</style>
""", unsafe_allow_html=True)

# ==================== FUNGSI UTILITY ====================

def get_file_info(data_dir="data"):
    """Get all CSV files with their dates from data folder"""
    data_path = Path(data_dir)
    data_path.mkdir(exist_ok=True)
    
    csv_files = []
    for file in data_path.glob("*.csv"):
        # Skip temporary or backup files
        if file.name.startswith('~') or file.name.startswith('.'):
            continue
            
        try:
            # Try to parse date from filename (format: YYYY-MM-DD.csv)
            date_str = file.stem[:10]
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            # Fallback to file modification time
            file_date = datetime.fromtimestamp(file.stat().st_mtime)
        
        csv_files.append({
            'path': str(file),
            'filename': file.name,
            'date': file_date,
            'date_str': file_date.strftime('%d %b %Y')
        })
    
    csv_files.sort(key=lambda x: x['date'], reverse=True)
    return csv_files

@st.cache_data(ttl=3600, show_spinner=False)
def load_data(filepath):
    """Load KSEI data from CSV file"""
    try:
        df = pd.read_csv(filepath)
        
        # Ensure required columns exist
        required_cols = ['SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 
                         'PERCENTAGE', 'TOTAL_HOLDING_SHARES', 'INVESTOR_TYPE']
        
        for col in required_cols:
            if col not in df.columns:
                st.error(f"Column '{col}' not found in {filepath}")
                return None
        
        # Use cleaned columns if available, otherwise use original
        if 'INVESTOR_NAME_CLEAN' in df.columns:
            investor_col = 'INVESTOR_NAME_CLEAN'
        else:
            investor_col = 'INVESTOR_NAME'
            df['INVESTOR_NAME_CLEAN'] = df['INVESTOR_NAME']
        
        if 'ISSUER_NAME_CLEAN' in df.columns:
            issuer_col = 'ISSUER_NAME_CLEAN'
        else:
            issuer_col = 'ISSUER_NAME'
            df['ISSUER_NAME_CLEAN'] = df['ISSUER_NAME']
        
        # Map investor types
        type_mapping = {
            'CP': 'Corporate',
            'ID': 'Individual',
            'MF': 'Mutual Funds',
            'PE': 'Private Equity',
            'IS': 'Insurance',
            'IB': 'Institutional',
            'SC': 'Securities',
            'FD': 'Foundation',
            'OT': 'Other',
            'PF': 'Pension Fund'
        }
        
        df['INVESTOR_CATEGORY'] = df['INVESTOR_TYPE'].map(type_mapping).fillna(df['INVESTOR_TYPE'])
        
        # Parse date from filename if not exists
        if 'SOURCE_DATE_STR' not in df.columns:
            filename = Path(filepath).stem
            try:
                date_str = filename[:10]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                df['SOURCE_DATE_STR'] = file_date.strftime('%d %b %Y')
            except:
                df['SOURCE_DATE_STR'] = filename
        
        return df
    except Exception as e:
        st.error(f"Error loading {filepath}: {str(e)}")
        return None

def create_investor_type_breakdown(df):
    """Create breakdown of ownership by investor type"""
    df = df.copy()
    
    # Aggregate by company and investor category
    breakdown = df.groupby(['SHARE_CODE', 'ISSUER_NAME_CLEAN', 'INVESTOR_CATEGORY']).agg({
        'PERCENTAGE': 'sum',
        'TOTAL_HOLDING_SHARES': 'sum'
    }).round(2).reset_index()
    
    # Pivot to get categories as columns
    pivot = breakdown.pivot_table(
        index=['SHARE_CODE', 'ISSUER_NAME_CLEAN'],
        columns='INVESTOR_CATEGORY',
        values='PERCENTAGE',
        fill_value=0
    ).reset_index()
    
    # Add total shares
    total_shares = df.groupby(['SHARE_CODE', 'ISSUER_NAME_CLEAN'])['TOTAL_HOLDING_SHARES'].sum().reset_index()
    total_shares.columns = ['SHARE_CODE', 'ISSUER_NAME_CLEAN', 'TOTAL_SHARES']
    
    # Merge
    result = total_shares.merge(pivot, on=['SHARE_CODE', 'ISSUER_NAME_CLEAN'], how='left')
    
    # Ensure all category columns exist
    all_categories = ['Corporate', 'Individual', 'Mutual Funds', 'Private Equity', 'Insurance', 
                      'Institutional', 'Securities', 'Foundation', 'Other', 'Pension Fund']
    
    for cat in all_categories:
        if cat not in result.columns:
            result[cat] = 0
    
    # Calculate total percentage
    result['TOTAL_%'] = result[all_categories].sum(axis=1).round(2)
    
    return result

def get_changes(df_old, df_new):
    """Get new and lost investors between two periods"""
    if df_old is None or df_new is None or df_old.empty or df_new.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    old_keys = set(df_old['SHARE_CODE'] + '|' + df_old['INVESTOR_NAME_CLEAN'])
    new_keys = set(df_new['SHARE_CODE'] + '|' + df_new['INVESTOR_NAME_CLEAN'])
    
    # New entries
    new_keys_list = list(new_keys - old_keys)
    new_entries = []
    for key in new_keys_list[:100]:
        code, name = key.split('|', 1)
        row = df_new[(df_new['SHARE_CODE'] == code) & (df_new['INVESTOR_NAME_CLEAN'] == name)]
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
    for key in lost_keys_list[:100]:
        code, name = key.split('|', 1)
        row = df_old[(df_old['SHARE_CODE'] == code) & (df_old['INVESTOR_NAME_CLEAN'] == name)]
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

def get_volume_changes(df_old, df_new):
    """Get investors with increased/decreased holdings between two periods"""
    if df_old is None or df_new is None or df_old.empty or df_new.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Merge on (SHARE_CODE, INVESTOR_NAME)
    merged = df_new.merge(
        df_old,
        on=['SHARE_CODE', 'INVESTOR_NAME_CLEAN'],
        how='inner',
        suffixes=('_new', '_old')
    )
    
    # Calculate changes
    merged['SHARES_CHANGE'] = merged['TOTAL_HOLDING_SHARES_new'] - merged['TOTAL_HOLDING_SHARES_old']
    merged['PCT_CHANGE'] = merged['PERCENTAGE_new'] - merged['PERCENTAGE_old']
    merged['SHARES_CHANGE_M'] = merged['SHARES_CHANGE'] / 1e6
    merged['PCT_CHANGE_ABS'] = abs(merged['PCT_CHANGE'])
    
    # Filter increases and decreases
    increased = merged[merged['SHARES_CHANGE'] > 0].copy()
    decreased = merged[merged['SHARES_CHANGE'] < 0].copy()
    
    # Sort by absolute change
    increased = increased.sort_values('SHARES_CHANGE', ascending=False)
    decreased = decreased.sort_values('SHARES_CHANGE', ascending=True)
    
    return increased, decreased

# ==================== LOAD DATA ====================

files_info = get_file_info("data")

if len(files_info) < 1:
    st.error("Tidak ada file CSV di folder 'data/'")
    st.info("""
    **Cara penggunaan:**
    1. Simpan file CSV hasil cleaning ke folder `data/`
    2. Format nama file: `YYYY-MM-DD.csv` (contoh: `2026-04-02.csv`)
    3. Pastikan file sudah memiliki kolom yang diperlukan
    """)
    st.stop()

# Load latest data
with st.spinner("Memuat data..."):
    latest_file = files_info[0]
    df_latest = load_data(latest_file['path'])
    
    if df_latest is None or df_latest.empty:
        st.error(f"Gagal memuat data dari {latest_file['filename']}")
        st.stop()
    
    latest_date = df_latest['SOURCE_DATE_STR'].iloc[0] if 'SOURCE_DATE_STR' in df_latest.columns else latest_file['date_str']
    
    # Load previous if exists
    df_previous = None
    prev_date = None
    if len(files_info) >= 2:
        prev_file = files_info[1]
        df_previous = load_data(prev_file['path'])
        if df_previous is not None and not df_previous.empty:
            prev_date = df_previous['SOURCE_DATE_STR'].iloc[0] if 'SOURCE_DATE_STR' in df_previous.columns else prev_file['date_str']
    
    # Get changes
    new_investors, lost_investors = get_changes(df_previous, df_latest)
    
    # Get volume changes
    increased_vol, decreased_vol = get_volume_changes(df_previous, df_latest)
    
    # Create breakdown
    breakdown_df = create_investor_type_breakdown(df_latest)

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

# ==================== VOLUME CHANGES SECTION (NEW!) ====================

if prev_date and (not increased_vol.empty or not decreased_vol.empty):
    st.markdown('<div class="section-header">📈 Perubahan Volume Kepemilikan</div>', unsafe_allow_html=True)
    
    tab_inc, tab_dec = st.tabs(["📈 Volume Naik (Top 15)", "📉 Volume Turun (Top 15)"])
    
    with tab_inc:
        if not increased_vol.empty:
            display_inc = increased_vol.head(15)[['INVESTOR_NAME_CLEAN', 'SHARE_CODE', 
                                                    'ISSUER_NAME_CLEAN_new', 'SHARES_CHANGE_M', 
                                                    'PCT_CHANGE', 'PERCENTAGE_new']]
            display_inc.columns = ['Investor', 'Kode Saham', 'Perusahaan', 'Perubahan (Juta)', 'Perubahan %', 'Posisi %']
            display_inc['Perubahan (Juta)'] = display_inc['Perubahan (Juta)'].round(0).astype(int)
            display_inc['Perubahan %'] = display_inc['Perubahan %'].round(2)
            display_inc['Posisi %'] = display_inc['Posisi %'].round(2)
            
            st.dataframe(display_inc, use_container_width=True, hide_index=True)
            
            # Chart for top increases
            fig_inc = px.bar(
                increased_vol.head(10),
                x='INVESTOR_NAME_CLEAN',
                y='SHARES_CHANGE_M',
                title="Top 10 Kenaikan Volume Saham (Juta)",
                color='PCT_CHANGE',
                color_continuous_scale='Greens',
                text='SHARES_CHANGE_M',
                labels={'INVESTOR_NAME_CLEAN': 'Investor', 'SHARES_CHANGE_M': 'Perubahan (Juta)'}
            )
            fig_inc.update_traces(texttemplate='%{text:.0f}', textposition='outside')
            fig_inc.update_layout(xaxis_tickangle=-45, height=400)
            st.plotly_chart(fig_inc, use_container_width=True)
        else:
            st.info("Tidak ada kenaikan volume kepemilikan")
    
    with tab_dec:
        if not decreased_vol.empty:
            display_dec = decreased_vol.head(15)[['INVESTOR_NAME_CLEAN', 'SHARE_CODE', 
                                                    'ISSUER_NAME_CLEAN_new', 'SHARES_CHANGE_M', 
                                                    'PCT_CHANGE', 'PERCENTAGE_new']]
            display_dec.columns = ['Investor', 'Kode Saham', 'Perusahaan', 'Perubahan (Juta)', 'Perubahan %', 'Posisi %']
            display_dec['Perubahan (Juta)'] = abs(display_dec['Perubahan (Juta)']).round(0).astype(int)
            display_dec['Perubahan %'] = display_dec['Perubahan %'].round(2)
            display_dec['Posisi %'] = display_dec['Posisi %'].round(2)
            
            st.dataframe(display_dec, use_container_width=True, hide_index=True)
            
            # Chart for top decreases
            fig_dec = px.bar(
                decreased_vol.head(10),
                x='INVESTOR_NAME_CLEAN',
                y='SHARES_CHANGE_M',
                title="Top 10 Penurunan Volume Saham (Juta)",
                color='PCT_CHANGE',
                color_continuous_scale='Reds',
                text='SHARES_CHANGE_M',
                labels={'INVESTOR_NAME_CLEAN': 'Investor', 'SHARES_CHANGE_M': 'Perubahan (Juta)'}
            )
            fig_dec.update_traces(texttemplate='%{text:.0f}', textposition='outside')
            fig_dec.update_layout(xaxis_tickangle=-45, height=400)
            st.plotly_chart(fig_dec, use_container_width=True)
        else:
            st.info("Tidak ada penurunan volume kepemilikan")

# ==================== NEW INVESTORS SECTION ====================

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

# ==================== TOP RANKINGS ====================

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
    top_investors = df_latest.groupby(['INVESTOR_NAME_CLEAN', 'INVESTOR_CATEGORY']).agg({
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

# ==================== INVESTOR TYPE BREAKDOWN ====================

st.markdown('<div class="section-header">📊 Breakdown Kepemilikan per Tipe Investor</div>', unsafe_allow_html=True)

# Filter for top companies
top_n_breakdown = st.selectbox("Tampilkan Top Perusahaan:", [10, 20, 50, 100], index=0, key="breakdown_top")

breakdown_sorted = breakdown_df.sort_values('TOTAL_SHARES', ascending=False).head(top_n_breakdown)
breakdown_sorted['TOTAL_SHARES (M)'] = (breakdown_sorted['TOTAL_SHARES'] / 1e6).round(0).astype(int)

# Select columns to display
category_cols = ['Corporate', 'Individual', 'Mutual Funds', 'Private Equity', 'Insurance']
existing_cols = [col for col in category_cols if col in breakdown_sorted.columns and breakdown_sorted[col].sum() > 0]

display_df = breakdown_sorted[['SHARE_CODE', 'ISSUER_NAME_CLEAN', 'TOTAL_SHARES (M)'] + existing_cols].copy()
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        'TOTAL_SHARES (M)': st.column_config.NumberColumn(label="Total Saham (Juta)", format="%d"),
        **{col: st.column_config.NumberColumn(format="%.2f%%") for col in existing_cols}
    }
)

# Stacked bar chart
st.subheader("Komposisi Kepemilikan per Tipe Investor")

chart_data = breakdown_sorted.head(10).copy()
chart_data['Company'] = chart_data['SHARE_CODE']

if existing_cols:
    fig = px.bar(
        chart_data,
        x='Company',
        y=existing_cols,
        title="Komposisi Kepemilikan (Top 10 Perusahaan)",
        labels={'value': 'Persentase (%)', 'variable': 'Tipe Investor'},
        barmode='stack',
        color_discrete_map={
            'Corporate': '#5470c6',
            'Individual': '#fac858',
            'Mutual Funds': '#ee6666',
            'Private Equity': '#73c0de',
            'Insurance': '#3ba272'
        }
    )
    fig.update_layout(xaxis_tickangle=-45, height=450, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
    st.plotly_chart(fig, use_container_width=True)

# Summary by investor type
st.subheader("Ringkasan per Tipe Investor")

type_summary = df_latest.groupby('INVESTOR_CATEGORY').agg({
    'PERCENTAGE': ['sum', 'mean', 'count'],
    'TOTAL_HOLDING_SHARES': 'sum'
}).round(2).reset_index()
type_summary.columns = ['Tipe Investor', 'Total_%', 'Rata-rata_%', 'Jumlah_Investor', 'Total_Saham']
type_summary['Total_Saham (M)'] = (type_summary['Total_Saham'] / 1e6).round(0).astype(int)
type_summary = type_summary.sort_values('Total_%', ascending=False)

col1, col2 = st.columns(2)
with col1:
    st.dataframe(type_summary[['Tipe Investor', 'Total_%', 'Jumlah_Investor', 'Total_Saham (M)']])
with col2:
    fig = px.pie(type_summary, values='Total_%', names='Tipe Investor', title="Distribusi Total Kepemilikan")
    st.plotly_chart(fig, use_container_width=True)

# ==================== COMPANY DETAIL ====================

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
        st.metric("📊 Total Kepemilikan", f"{company_data['PERCENTAGE'].sum():.2f}%")
    with col3:
        st.metric("🏆 Terbesar", f"{company_data['PERCENTAGE'].max():.2f}%")
    with col4:
        st.metric("💰 Total Saham", f"{company_data['TOTAL_HOLDING_SHARES'].sum() / 1e6:.1f}Jt")
    
    # Breakdown by investor type for this company
    st.markdown('<div class="sub-section-header">📊 Breakdown Tipe Investor</div>', unsafe_allow_html=True)
    
    company_breakdown = company_data.groupby('INVESTOR_CATEGORY').agg({
        'PERCENTAGE': 'sum',
        'TOTAL_HOLDING_SHARES': 'sum',
        'INVESTOR_NAME_CLEAN': 'count'
    }).round(2).reset_index()
    company_breakdown.columns = ['Tipe', 'Total_%', 'Total_Saham', 'Jumlah_Investor']
    company_breakdown['Saham (M)'] = (company_breakdown['Total_Saham'] / 1e6).round(0).astype(int)
    
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(company_breakdown[['Tipe', 'Total_%', 'Jumlah_Investor', 'Saham (M)']])
    with col2:
        fig = px.pie(company_breakdown, values='Total_%', names='Tipe', title=f"Komposisi Investor {selected_company}")
        st.plotly_chart(fig, use_container_width=True)
    
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
            
            # Show volume changes for this company
            company_vol_changes = increased_vol[increased_vol['SHARE_CODE'] == selected_company] if not increased_vol.empty else pd.DataFrame()
            company_vol_changes_dec = decreased_vol[decreased_vol['SHARE_CODE'] == selected_company] if not decreased_vol.empty else pd.DataFrame()
            
            if not company_vol_changes.empty or not company_vol_changes_dec.empty:
                st.markdown("**📊 Perubahan Volume di Perusahaan Ini:**")
                vol_col1, vol_col2 = st.columns(2)
                with vol_col1:
                    if not company_vol_changes.empty:
                        st.markdown("📈 **Volume Naik:**")
                        for _, row in company_vol_changes.head(5).iterrows():
                            st.success(f"{row['INVESTOR_NAME_CLEAN']}: +{row['SHARES_CHANGE_M']:.0f}Jt ({row['PCT_CHANGE']:+.2f}%)")
                with vol_col2:
                    if not company_vol_changes_dec.empty:
                        st.markdown("📉 **Volume Turun:**")
                        for _, row in company_vol_changes_dec.head(5).iterrows():
                            st.error(f"{row['INVESTOR_NAME_CLEAN']}: {row['SHARES_CHANGE_M']:.0f}Jt ({row['PCT_CHANGE']:+.2f}%)")
    
    # Investor list
    st.markdown('<div class="sub-section-header">📋 Daftar Investor</div>', unsafe_allow_html=True)
    st.dataframe(
        company_data[['INVESTOR_NAME_CLEAN', 'PERCENTAGE', 'TOTAL_HOLDING_SHARES', 'INVESTOR_CATEGORY']]
        .sort_values('PERCENTAGE', ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            'PERCENTAGE': st.column_config.NumberColumn(format="%.2f%%"),
            'TOTAL_HOLDING_SHARES': st.column_config.NumberColumn(format="%d")
        }
    )
    
    # Chart
    fig = px.bar(company_data.head(15), x='INVESTOR_NAME_CLEAN', y='PERCENTAGE',
                 title=f"Top Investor di {selected_company}", color='PERCENTAGE',
                 color_continuous_scale='Viridis', text='PERCENTAGE')
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(xaxis_tickangle=-45, height=400)
    st.plotly_chart(fig, use_container_width=True)

# ==================== INVESTOR DETAIL ====================

st.markdown('<div class="section-header">🔍 Detail Investor</div>', unsafe_allow_html=True)

investors = sorted(df_latest['INVESTOR_NAME_CLEAN'].unique())
selected_investor = st.selectbox("Pilih Investor:", investors, key="investor_select")

if selected_investor:
    investor_data = df_latest[df_latest['INVESTOR_NAME_CLEAN'] == selected_investor].copy()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏢 Perusahaan", len(investor_data))
    with col2:
        st.metric("📊 Total Kepemilikan", f"{investor_data['PERCENTAGE'].sum():.2f}%")
    with col3:
        st.metric("💰 Total Saham", f"{investor_data['TOTAL_HOLDING_SHARES'].sum() / 1e6:.1f}Jt")
    with col4:
        tipe = investor_data['INVESTOR_CATEGORY'].iloc[0] if not investor_data.empty else '-'
        st.metric("🏷️ Tipe", tipe)
    
    # Breakdown by sector/type for this investor
    st.markdown('<div class="sub-section-header">📊 Distribusi Portfolio</div>', unsafe_allow_html=True)
    
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
            
            # Show volume changes for this investor
            investor_vol_changes = increased_vol[increased_vol['INVESTOR_NAME_CLEAN'] == selected_investor] if not increased_vol.empty else pd.DataFrame()
            investor_vol_changes_dec = decreased_vol[decreased_vol['INVESTOR_NAME_CLEAN'] == selected_investor] if not decreased_vol.empty else pd.DataFrame()
            
            if not investor_vol_changes.empty or not investor_vol_changes_dec.empty:
                st.markdown("**📊 Perubahan Volume Investor Ini:**")
                vol_col1, vol_col2 = st.columns(2)
                with vol_col1:
                    if not investor_vol_changes.empty:
                        st.markdown("📈 **Volume Naik:**")
                        for _, row in investor_vol_changes.head(5).iterrows():
                            st.success(f"{row['SHARE_CODE']}: +{row['SHARES_CHANGE_M']:.0f}Jt ({row['PCT_CHANGE']:+.2f}%)")
                with vol_col2:
                    if not investor_vol_changes_dec.empty:
                        st.markdown("📉 **Volume Turun:**")
                        for _, row in investor_vol_changes_dec.head(5).iterrows():
                            st.error(f"{row['SHARE_CODE']}: {row['SHARES_CHANGE_M']:.0f}Jt ({row['PCT_CHANGE']:+.2f}%)")
    
    # Portfolio list
    st.markdown('<div class="sub-section-header">📋 Portfolio</div>', unsafe_allow_html=True)
    st.dataframe(
        investor_data[['SHARE_CODE', 'ISSUER_NAME_CLEAN', 'PERCENTAGE', 'TOTAL_HOLDING_SHARES', 'INVESTOR_CATEGORY']]
        .sort_values('PERCENTAGE', ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            'PERCENTAGE': st.column_config.NumberColumn(format="%.2f%%"),
            'TOTAL_HOLDING_SHARES': st.column_config.NumberColumn(format="%d")
        }
    )

# ==================== SUMMARY STATISTICS ====================

st.markdown('<div class="section-header">📊 Ringkasan Perubahan</div>', unsafe_allow_html=True)

if prev_date:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🆕 Investor Baru", len(new_investors))
    with col2:
        st.metric("❌ Investor Keluar", len(lost_investors))
    with col3:
        st.metric("📈 Volume Naik", len(increased_vol))
    with col4:
        st.metric("📉 Volume Turun", len(decreased_vol))
    
    # Total volume change summary
    total_increase = increased_vol['SHARES_CHANGE'].sum() / 1e6 if not increased_vol.empty else 0
    total_decrease = abs(decreased_vol['SHARES_CHANGE'].sum()) / 1e6 if not decreased_vol.empty else 0
    net_change = total_increase - total_decrease
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📈 Total Volume Naik: **{total_increase:.1f} Juta saham**")
    with col2:
        st.warning(f"📉 Total Volume Turun: **{total_decrease:.1f} Juta saham**")
    with col3:
        delta_color = "green" if net_change >= 0 else "red"
        st.markdown(f"⚖️ **Net Perubahan: <span style='color:{delta_color}'>{net_change:+.1f} Juta saham</span>**", unsafe_allow_html=True)
else:
    st.info("Perbandingan dengan periode sebelumnya tidak tersedia. Upload minimal 2 file CSV untuk melihat ringkasan perubahan.")

# Footer
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("📊 KSEI Analytics Dashboard")
with col2:
    st.caption(f"📅 Data: {latest_date}" + (f" (vs {prev_date})" if prev_date else ""))
with col3:
    st.caption("🎯 Kepemilikan >1% | Data dari KSEI")