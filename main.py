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
    page_title="KSEI Changes Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom CSS untuk styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .positive-change {
        color: #28a745;
        font-weight: bold;
    }
    .negative-change {
        color: #dc3545;
        font-weight: bold;
    }
    .big-number {
        font-size: 32px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("📊 KSEI Shareholder Changes Tracker")
st.caption("Track perubahan kepemilikan saham >5% antar periode")

# Initialize session state
if 'selected_company' not in st.session_state:
    st.session_state.selected_company = None

# Fungsi untuk mendapatkan semua file CSV
@st.cache_data(ttl=60)
def get_all_files(data_dir="data"):
    """Mengambil semua file CSV dari folder data"""
    Path(data_dir).mkdir(exist_ok=True)
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        return []
    
    # Parse tanggal dari nama file
    files_with_dates = []
    for file in csv_files:
        filename = os.path.basename(file)
        try:
            date_str = filename.replace('.csv', '')
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            files_with_dates.append((file, filename, file_date))
        except:
            file_date = datetime.fromtimestamp(os.path.getmtime(file))
            files_with_dates.append((file, filename, file_date))
    
    files_with_dates.sort(key=lambda x: x[2], reverse=True)
    return files_with_dates

# Fungsi untuk load data
@st.cache_data(ttl=60)
def load_data_file(filepath):
    """Load data dari file CSV"""
    try:
        df = pd.read_csv(filepath, header=None, skiprows=1)
        df.columns = ['DATE', 'SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 
                      'INVESTOR_TYPE', 'LOCAL_FOREIGN', 'NATIONALITY', 'DOMICILE',
                      'HOLDINGS_SCRIPLESS', 'HOLDINGS_SCRIP', 'TOTAL_HOLDING_SHARES', 
                      'PERCENTAGE', 'EXTRA']
        
        if 'EXTRA' in df.columns:
            df = df.drop('EXTRA', axis=1)
        
        # Bersihkan data
        df = df[~df['SHARE_CODE'].astype(str).str.contains('SHARE_CODE', na=False)]
        df['DATE'] = pd.to_datetime(df['DATE'], format='%d-%b-%Y', errors='coerce')
        
        # Convert PERCENTAGE
        df['PERCENTAGE'] = df['PERCENTAGE'].astype(str).str.replace('"', '').str.replace(',', '.').str.strip()
        df['PERCENTAGE'] = pd.to_numeric(df['PERCENTAGE'], errors='coerce')
        
        # Bersihkan nama perusahaan dan investor
        df['SHARE_CODE'] = df['SHARE_CODE'].astype(str).str.strip()
        df['ISSUER_NAME'] = df['ISSUER_NAME'].astype(str).str.strip()
        df['INVESTOR_NAME'] = df['INVESTOR_NAME'].astype(str).str.strip()
        
        df = df.dropna(subset=['SHARE_CODE', 'PERCENTAGE'])
        return df
    except Exception as e:
        st.error(f"Error loading {filepath}: {str(e)}")
        return None

# Fungsi untuk membandingkan dengan fokus pada perubahan besar
def compare_datasets_v2(df_old, df_new, old_date, new_date, min_change_threshold=0.5):
    """
    Membandingkan dua dataset dengan fokus pada perubahan signifikan
    min_change_threshold: minimum perubahan persentase untuk dicatat (%)
    """
    
    # Buat key yang lebih robust
    df_old = df_old.copy()
    df_new = df_new.copy()
    
    # Normalize strings untuk matching yang lebih baik
    df_old['SHARE_CODE'] = df_old['SHARE_CODE'].str.upper().str.strip()
    df_old['INVESTOR_NAME'] = df_old['INVESTOR_NAME'].str.upper().str.strip()
    df_new['SHARE_CODE'] = df_new['SHARE_CODE'].str.upper().str.strip()
    df_new['INVESTOR_NAME'] = df_new['INVESTOR_NAME'].str.upper().str.strip()
    
    df_old['KEY'] = df_old['SHARE_CODE'] + '|' + df_old['INVESTOR_NAME']
    df_new['KEY'] = df_new['SHARE_CODE'] + '|' + df_new['INVESTOR_NAME']
    
    old_keys = set(df_old['KEY'].unique())
    new_keys = set(df_new['KEY'].unique())
    
    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = old_keys & new_keys
    
    changes = []
    
    # Data yang bertambah
    for key in added_keys:
        row = df_new[df_new['KEY'] == key].iloc[0]
        if row['PERCENTAGE'] >= min_change_threshold:  # Hanya catat jika > threshold
            changes.append({
                'SHARE_CODE': row['SHARE_CODE'],
                'ISSUER_NAME': row['ISSUER_NAME'],
                'INVESTOR_NAME': row['INVESTOR_NAME'],
                'TYPE': 'ADDED',
                'OLD_%': 0,
                'NEW_%': row['PERCENTAGE'],
                'CHANGE_%': row['PERCENTAGE'],
                'OLD_DATE': old_date,
                'NEW_DATE': new_date,
                'INVESTOR_TYPE': row.get('INVESTOR_TYPE', ''),
                'LOCAL_FOREIGN': row.get('LOCAL_FOREIGN', '')
            })
    
    # Data yang berkurang
    for key in removed_keys:
        row = df_old[df_old['KEY'] == key].iloc[0]
        if row['PERCENTAGE'] >= min_change_threshold:
            changes.append({
                'SHARE_CODE': row['SHARE_CODE'],
                'ISSUER_NAME': row['ISSUER_NAME'],
                'INVESTOR_NAME': row['INVESTOR_NAME'],
                'TYPE': 'REMOVED',
                'OLD_%': row['PERCENTAGE'],
                'NEW_%': 0,
                'CHANGE_%': -row['PERCENTAGE'],
                'OLD_DATE': old_date,
                'NEW_DATE': new_date,
                'INVESTOR_TYPE': row.get('INVESTOR_TYPE', ''),
                'LOCAL_FOREIGN': row.get('LOCAL_FOREIGN', '')
            })
    
    # Data yang berubah
    for key in common_keys:
        old_row = df_old[df_old['KEY'] == key].iloc[0]
        new_row = df_new[df_new['KEY'] == key].iloc[0]
        
        old_pct = old_row['PERCENTAGE']
        new_pct = new_row['PERCENTAGE']
        change = new_pct - old_pct
        
        if abs(change) >= min_change_threshold:
            changes.append({
                'SHARE_CODE': old_row['SHARE_CODE'],
                'ISSUER_NAME': old_row['ISSUER_NAME'],
                'INVESTOR_NAME': old_row['INVESTOR_NAME'],
                'TYPE': 'CHANGED',
                'OLD_%': old_pct,
                'NEW_%': new_pct,
                'CHANGE_%': change,
                'OLD_DATE': old_date,
                'NEW_DATE': new_date,
                'INVESTOR_TYPE': old_row.get('INVESTOR_TYPE', ''),
                'LOCAL_FOREIGN': old_row.get('LOCAL_FOREIGN', '')
            })
    
    if changes:
        changes_df = pd.DataFrame(changes)
        return changes_df.sort_values('CHANGE_%', ascending=False)
    else:
        return pd.DataFrame()

# Load semua file
all_files = get_all_files()

# Sidebar
with st.sidebar:
    st.header("⚙️ Pengaturan")
    
    if all_files and len(all_files) >= 2:
        # Pilihan periode
        st.subheader("📅 Pilih Periode")
        file_options = [f"{f[2].strftime('%d-%b-%Y')} ({f[1]})" for f in all_files]
        
        col1, col2 = st.columns(2)
        with col1:
            new_idx = st.selectbox(
                "Periode Baru",
                range(len(file_options)),
                format_func=lambda x: all_files[x][2].strftime('%d-%b-%Y'),
                index=0
            )
        with col2:
            old_idx = st.selectbox(
                "Periode Lama",
                range(len(file_options)),
                format_func=lambda x: all_files[x][2].strftime('%d-%b-%Y'),
                index=1 if len(all_files) > 1 else 0
            )
        
        # Load data
        df_new = load_data_file(all_files[new_idx][0])
        df_old = load_data_file(all_files[old_idx][0])
        
        if df_new is not None and df_old is not None:
            new_date = all_files[new_idx][2].strftime('%d-%b-%Y')
            old_date = all_files[old_idx][2].strftime('%d-%b-%Y')
            
            st.success(f"📊 {old_date} → {new_date}")
            
            # Filter penting
            st.subheader("🎯 Filter")
            
            # Threshold untuk perubahan
            min_change = st.slider(
                "Min. Perubahan (%)",
                min_value=0.1,
                max_value=10.0,
                value=0.5,
                step=0.1,
                help="Hanya tampilkan perubahan di atas nilai ini"
            )
            
            # Filter berdasarkan tipe
            show_types = st.multiselect(
                "Tipe Perubahan",
                options=['ADDED', 'REMOVED', 'CHANGED'],
                default=['ADDED', 'REMOVED', 'CHANGED'],
                format_func=lambda x: {
                    'ADDED': '➕ Bertambah',
                    'REMOVED': '➖ Berkurang',
                    'CHANGED': '🔄 Berubah'
                }[x]
            )
            
            # Search box
            search = st.text_input("🔍 Cari Perusahaan/Investor", "")
            
            # Info data
            st.divider()
            st.caption(f"Total data {new_date}: {len(df_new):,}")
            st.caption(f"Total data {old_date}: {len(df_old):,}")
            
    else:
        st.warning("Minimal 2 file CSV diperlukan")
        st.info("Format file: YYYY-MM-DD.csv")
        df_new = df_old = None

# Main content
if df_new is not None and df_old is not None and len(all_files) >= 2:
    
    # Hitung perubahan dengan threshold yang bisa diatur
    changes_df = compare_datasets_v2(
        df_old, df_new, old_date, new_date, 
        min_change_threshold=min_change
    )
    
    # Apply filters
    if not changes_df.empty:
        if show_types:
            changes_df = changes_df[changes_df['TYPE'].isin(show_types)]
        
        if search:
            changes_df = changes_df[
                changes_df['SHARE_CODE'].str.contains(search.upper(), na=False) |
                changes_df['INVESTOR_NAME'].str.contains(search.upper(), na=False) |
                changes_df['ISSUER_NAME'].str.contains(search.upper(), na=False)
            ]
    
    # Dashboard Utama
    st.header(f"📈 Perubahan Kepemilikan Saham >{min_change}%")
    
    if not changes_df.empty:
        # Key Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_changes = len(changes_df)
            st.metric("Total Perubahan", f"{total_changes}")
        
        with col2:
            added = len(changes_df[changes_df['TYPE'] == 'ADDED'])
            st.metric("➕ Bertambah", added)
        
        with col3:
            removed = len(changes_df[changes_df['TYPE'] == 'REMOVED'])
            st.metric("➖ Berkurang", removed)
        
        with col4:
            changed = len(changes_df[changes_df['TYPE'] == 'CHANGED'])
            st.metric("🔄 Berubah", changed)
        
        with col5:
            net_change = changes_df['CHANGE_%'].sum()
            st.metric("💰 Net Change", f"{net_change:+.2f}%")
        
        st.divider()
        
        # Tabs untuk visualisasi
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Overview", 
            "🏢 Perusahaan", 
            "👤 Investor", 
            "📋 Detail Perubahan",
            "📈 Top Movers"
        ])
        
        with tab1:  # Overview
            st.subheader("Ringkasan Perubahan")
            
            # Summary by company
            company_summary = changes_df.groupby(['SHARE_CODE', 'ISSUER_NAME']).agg({
                'CHANGE_%': 'sum'
            }).round(2)
            
            # Hitung counts per tipe
            for tipe in ['ADDED', 'REMOVED', 'CHANGED']:
                count = changes_df[changes_df['TYPE'] == tipe].groupby('SHARE_CODE').size()
                company_summary[tipe] = count
            
            company_summary = company_summary.fillna(0).astype({
                'ADDED': int, 'REMOVED': int, 'CHANGED': int
            }).sort_values('CHANGE_%', ascending=False).reset_index()
            
            # Top 10 perubahan
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### 📈 Top 10 Kenaikan Bersih")
                top_up = company_summary.nlargest(10, 'CHANGE_%')[['SHARE_CODE', 'ISSUER_NAME', 'CHANGE_%']]
                if not top_up.empty:
                    fig = px.bar(
                        top_up,
                        x='CHANGE_%',
                        y='SHARE_CODE',
                        orientation='h',
                        color='CHANGE_%',
                        color_continuous_scale='Greens',
                        labels={'CHANGE_%': 'Net Change (%)', 'SHARE_CODE': 'Company'}
                    )
                    fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("##### 📉 Top 10 Penurunan Bersih")
                top_down = company_summary.nsmallest(10, 'CHANGE_%')[['SHARE_CODE', 'ISSUER_NAME', 'CHANGE_%']]
                if not top_down.empty:
                    fig = px.bar(
                        top_down,
                        x='CHANGE_%',
                        y='SHARE_CODE',
                        orientation='h',
                        color='CHANGE_%',
                        color_continuous_scale='Reds',
                        labels={'CHANGE_%': 'Net Change (%)', 'SHARE_CODE': 'Company'}
                    )
                    fig.update_layout(yaxis={'categoryorder':'total descending'}, height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Distribution pie
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                type_dist = changes_df['TYPE'].value_counts()
                fig = px.pie(
                    values=type_dist.values,
                    names=type_dist.index,
                    title="Distribusi Tipe Perubahan",
                    color=type_dist.index,
                    color_discrete_map={
                        'ADDED': '#28a745',
                        'REMOVED': '#dc3545',
                        'CHANGED': '#ffc107'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                if 'LOCAL_FOREIGN' in changes_df.columns:
                    lf_dist = changes_df['LOCAL_FOREIGN'].value_counts()
                    fig = px.pie(
                        values=lf_dist.values,
                        names=lf_dist.index,
                        title="Distribusi Lokal/Asing",
                        color=lf_dist.index,
                        color_discrete_map={
                            'L': '#28a745',
                            'A': '#ffc107'
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        with tab2:  # Perusahaan
            st.subheader("Analisis per Perusahaan")
            
            # Pilih perusahaan
            companies = sorted(changes_df['SHARE_CODE'].unique())
            selected_company = st.selectbox(
                "Pilih Perusahaan",
                companies,
                key="company_select"
            )
            
            if selected_company:
                company_data = changes_df[changes_df['SHARE_CODE'] == selected_company].copy()
                company_name = company_data['ISSUER_NAME'].iloc[0]
                
                st.markdown(f"### {selected_company} - {company_name}")
                
                # Metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Perubahan", len(company_data))
                with col2:
                    st.metric("Net Change", f"{company_data['CHANGE_%'].sum():+.2f}%")
                with col3:
                    added_company = len(company_data[company_data['TYPE'] == 'ADDED'])
                    st.metric("Bertambah", added_company)
                with col4:
                    removed_company = len(company_data[company_data['TYPE'] == 'REMOVED'])
                    st.metric("Berkurang", removed_company)
                
                # Detail
                st.markdown("#### Detail Perubahan")
                display_cols = ['INVESTOR_NAME', 'TYPE', 'OLD_%', 'NEW_%', 'CHANGE_%', 'LOCAL_FOREIGN']
                display_df = company_data[display_cols].sort_values('CHANGE_%', ascending=False)
                display_df['OLD_%'] = display_df['OLD_%'].round(2)
                display_df['NEW_%'] = display_df['NEW_%'].round(2)
                display_df['CHANGE_%'] = display_df['CHANGE_%'].round(2)
                st.dataframe(display_df, use_container_width=True)
                
                # Visualisasi
                fig = px.bar(
                    company_data,
                    x='INVESTOR_NAME',
                    y='CHANGE_%',
                    color='TYPE',
                    title=f"Perubahan per Investor - {selected_company}",
                    color_discrete_map={
                        'ADDED': '#28a745',
                        'REMOVED': '#dc3545',
                        'CHANGED': '#ffc107'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with tab3:  # Investor
            st.subheader("Analisis per Investor")
            
            # Pilih investor
            investors = sorted(changes_df['INVESTOR_NAME'].unique())
            selected_investor = st.selectbox(
                "Pilih Investor",
                investors,
                key="investor_select"
            )
            
            if selected_investor:
                investor_data = changes_df[changes_df['INVESTOR_NAME'] == selected_investor].copy()
                
                st.markdown(f"### {selected_investor}")
                
                # Metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Perusahaan Terpengaruh", len(investor_data))
                with col2:
                    st.metric("Total Perubahan", f"{investor_data['CHANGE_%'].sum():+.2f}%")
                with col3:
                    st.metric("Rata-rata Perubahan", f"{investor_data['CHANGE_%'].mean():+.2f}%")
                
                # Detail
                st.markdown("#### Portfolio Changes")
                display_cols = ['SHARE_CODE', 'ISSUER_NAME', 'TYPE', 'OLD_%', 'NEW_%', 'CHANGE_%']
                display_df = investor_data[display_cols].sort_values('CHANGE_%', ascending=False)
                display_df['OLD_%'] = display_df['OLD_%'].round(2)
                display_df['NEW_%'] = display_df['NEW_%'].round(2)
                display_df['CHANGE_%'] = display_df['CHANGE_%'].round(2)
                st.dataframe(display_df, use_container_width=True)
        
        with tab4:  # Detail Perubahan
            st.subheader("📋 Semua Perubahan")
            
            # Format untuk display
            display_df = changes_df.copy()
            display_df['OLD_%'] = display_df['OLD_%'].round(2)
            display_df['NEW_%'] = display_df['NEW_%'].round(2)
            display_df['CHANGE_%'] = display_df['CHANGE_%'].round(2)
            
            # Color code based on change
            def color_change(val):
                if val > 0:
                    return 'background-color: #d4edda'
                elif val < 0:
                    return 'background-color: #f8d7da'
                return ''
            
            st.dataframe(
                display_df.style.applymap(color_change, subset=['CHANGE_%']),
                use_container_width=True,
                height=500
            )
            
            # Download button
            csv = changes_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Data Perubahan",
                csv,
                f"ksei_changes_{old_date}_to_{new_date}.csv",
                "text/csv",
                use_container_width=True
            )
        
        with tab5:  # Top Movers
            st.subheader("📈 Top Movers")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🟢 Top 20 Kenaikan")
                top_gainers = changes_df.nlargest(20, 'CHANGE_%')[
                    ['SHARE_CODE', 'INVESTOR_NAME', 'CHANGE_%', 'TYPE']
                ]
                if not top_gainers.empty:
                    top_gainers['CHANGE_%'] = top_gainers['CHANGE_%'].round(2)
                    top_gainers.index = range(1, len(top_gainers) + 1)
                    st.dataframe(top_gainers, use_container_width=True)
            
            with col2:
                st.markdown("#### 🔴 Top 20 Penurunan")
                top_losers = changes_df.nsmallest(20, 'CHANGE_%')[
                    ['SHARE_CODE', 'INVESTOR_NAME', 'CHANGE_%', 'TYPE']
                ]
                if not top_losers.empty:
                    top_losers['CHANGE_%'] = top_losers['CHANGE_%'].round(2)
                    top_losers.index = range(1, len(top_losers) + 1)
                    st.dataframe(top_losers, use_container_width=True)
            
            # Scatter plot perubahan
            st.divider()
            st.markdown("#### Distribusi Perubahan")
            
            fig = px.histogram(
                changes_df,
                x='CHANGE_%',
                nbins=50,
                title="Distribusi Nilai Perubahan",
                labels={'CHANGE_%': 'Perubahan (%)', 'count': 'Jumlah'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info(f"Tidak ada perubahan signifikan (> {min_change}%) antara {old_date} dan {new_date}")
        
        # Tampilkan sample data untuk debugging
        with st.expander("Debug: Lihat sample data"):
            st.write("Sample data old:", df_old[['SHARE_CODE', 'INVESTOR_NAME', 'PERCENTAGE']].head())
            st.write("Sample data new:", df_new[['SHARE_CODE', 'INVESTOR_NAME', 'PERCENTAGE']].head())

else:
    st.info("📁 Letakkan minimal 2 file CSV di folder `data/`")
    st.markdown("""
    ## Cara Penggunaan:
    1. Buat folder `data/` di direktori yang sama
    2. Letakkan file CSV dengan format: **YYYY-MM-DD.csv**
    3. Pilih dua periode untuk dibandingkan
    
    ## Fitur:
    - 📊 **Overview** - Ringkasan perubahan
    - 🏢 **Perusahaan** - Analisis per perusahaan
    - 👤 **Investor** - Tracking per investor
    - 📋 **Detail** - Semua perubahan dalam tabel
    - 📈 **Top Movers** - Kenaikan/penurunan terbesar
    """)

# Footer
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("Data source: KSEI")
with col2:
    if all_files:
        st.caption(f"Total periode: {len(all_files)}")
with col3:
    st.caption("v2.0 - Changes Tracker")