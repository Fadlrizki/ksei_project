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
    page_title="KSEI Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2563EB;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .card {
        background-color: #F3F4F6;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .positive {
        color: #059669;
        font-weight: bold;
    }
    .negative {
        color: #DC2626;
        font-weight: bold;
    }
    .dropdown-container {
        background: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .metric-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<p class="main-header">📊 KSEI Shareholder Dashboard ( >1% Ownership )</p>', unsafe_allow_html=True)
st.caption("Analisis kepemilikan saham >1% - Data terkini dan perubahan antar periode")

# Initialize session state
if 'selected_company' not in st.session_state:
    st.session_state.selected_company = None
if 'selected_investor' not in st.session_state:
    st.session_state.selected_investor = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "📅 Data Terkini"
if 'search_company' not in st.session_state:
    st.session_state.search_company = ""
if 'search_investor' not in st.session_state:
    st.session_state.search_investor = ""

# Fungsi untuk mendapatkan semua file CSV
@st.cache_data(ttl=60)
def get_all_files(data_dir="data"):
    Path(data_dir).mkdir(exist_ok=True)
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        return []
    
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
        
        # Filter >1%
        df = df[df['PERCENTAGE'] > 1]
        
        # Bersihkan string
        str_cols = ['SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 'INVESTOR_TYPE', 'LOCAL_FOREIGN']
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        df = df.dropna(subset=['SHARE_CODE', 'PERCENTAGE'])
        return df
    except Exception as e:
        st.error(f"Error loading {filepath}: {str(e)}")
        return None

# Fungsi untuk membandingkan dataset
def compare_datasets(df_old, df_new, old_date, new_date):
    df_old = df_old.copy()
    df_new = df_new.copy()
    
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
    
    for key in added_keys:
        row = df_new[df_new['KEY'] == key].iloc[0]
        changes.append({
            'SHARE_CODE': row['SHARE_CODE'],
            'ISSUER_NAME': row['ISSUER_NAME'],
            'INVESTOR_NAME': row['INVESTOR_NAME'],
            'TYPE': 'BERTAMBAH',
            'OLD_%': 0,
            'NEW_%': row['PERCENTAGE'],
            'CHANGE_%': row['PERCENTAGE'],
            'OLD_DATE': old_date,
            'NEW_DATE': new_date,
            'INVESTOR_TYPE': row.get('INVESTOR_TYPE', ''),
            'LOCAL_FOREIGN': row.get('LOCAL_FOREIGN', '')
        })
    
    for key in removed_keys:
        row = df_old[df_old['KEY'] == key].iloc[0]
        changes.append({
            'SHARE_CODE': row['SHARE_CODE'],
            'ISSUER_NAME': row['ISSUER_NAME'],
            'INVESTOR_NAME': row['INVESTOR_NAME'],
            'TYPE': 'BERKURANG',
            'OLD_%': row['PERCENTAGE'],
            'NEW_%': 0,
            'CHANGE_%': -row['PERCENTAGE'],
            'OLD_DATE': old_date,
            'NEW_DATE': new_date,
            'INVESTOR_TYPE': row.get('INVESTOR_TYPE', ''),
            'LOCAL_FOREIGN': row.get('LOCAL_FOREIGN', '')
        })
    
    for key in common_keys:
        old_row = df_old[df_old['KEY'] == key].iloc[0]
        new_row = df_new[df_new['KEY'] == key].iloc[0]
        
        old_pct = old_row['PERCENTAGE']
        new_pct = new_row['PERCENTAGE']
        change = new_pct - old_pct
        
        if abs(change) > 0.01:
            changes.append({
                'SHARE_CODE': old_row['SHARE_CODE'],
                'ISSUER_NAME': old_row['ISSUER_NAME'],
                'INVESTOR_NAME': old_row['INVESTOR_NAME'],
                'TYPE': 'BERUBAH',
                'OLD_%': old_pct,
                'NEW_%': new_pct,
                'CHANGE_%': change,
                'OLD_DATE': old_date,
                'NEW_DATE': new_date,
                'INVESTOR_TYPE': old_row.get('INVESTOR_TYPE', ''),
                'LOCAL_FOREIGN': old_row.get('LOCAL_FOREIGN', '')
            })
    
    if changes:
        return pd.DataFrame(changes)
    return pd.DataFrame()

# Load semua file
all_files = get_all_files()

# Sidebar Navigation
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/combo-chart--v1.png", width=80)
    st.markdown("## Menu Utama")
    
    view_options = ["📅 Data Terkini", "🔄 Perubahan", "🏢 Perusahaan", "👥 Investor"]
    view_mode = st.radio(
        "Pilih Tampilan:",
        view_options,
        key="view_mode_radio",
        index=0
    )
    
    st.divider()
    
    if all_files:
        st.markdown("### 📁 Data Tersedia")
        for i, (_, filename, date) in enumerate(all_files[:3]):
            if i == 0:
                st.success(f"📌 Terbaru: {date.strftime('%d-%b-%Y')}")
            else:
                st.info(f"📅 {date.strftime('%d-%b-%Y')}")
        
        df_latest = load_data_file(all_files[0][0])
        latest_date = all_files[0][2].strftime('%d-%b-%Y')
        
        if len(all_files) >= 2:
            df_previous = load_data_file(all_files[1][0])
            previous_date = all_files[1][2].strftime('%d-%b-%Y')
        else:
            df_previous = None
            previous_date = None
            
        # Quick stats di sidebar
        if df_latest is not None:
            st.divider()
            st.markdown("### 📊 Quick Stats")
            st.metric("Total Perusahaan", df_latest['SHARE_CODE'].nunique())
            st.metric("Total Investor", df_latest['INVESTOR_NAME'].nunique())
            st.metric("Rata-rata %", f"{df_latest['PERCENTAGE'].mean():.2f}%")
    else:
        st.warning("Tidak ada file CSV di folder data/")
        df_latest = df_previous = None
        latest_date = previous_date = None

# Main content
if df_latest is not None:
    
    if view_mode == "📅 Data Terkini":
        # ==================== DATA TERKINI ====================
        st.markdown(f'<p class="sub-header">📅 Data Kepemilikan Saham >1% per {latest_date}</p>', unsafe_allow_html=True)
        
        # Key Metrics dengan card yang lebih menarik
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-container">
                <div style="font-size: 1rem; opacity: 0.9;">Total Perusahaan</div>
                <div style="font-size: 2.5rem; font-weight: bold;">{df_latest['SHARE_CODE'].nunique():,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-container">
                <div style="font-size: 1rem; opacity: 0.9;">Total Investor</div>
                <div style="font-size: 2.5rem; font-weight: bold;">{df_latest['INVESTOR_NAME'].nunique():,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-container">
                <div style="font-size: 1rem; opacity: 0.9;">Rata-rata Kepemilikan</div>
                <div style="font-size: 2.5rem; font-weight: bold;">{df_latest['PERCENTAGE'].mean():.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-container">
                <div style="font-size: 1rem; opacity: 0.9;">Total Kepemilikan</div>
                <div style="font-size: 2.5rem; font-weight: bold;">{df_latest['PERCENTAGE'].sum():.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Filter dengan dropdown untuk memudahkan pencarian
        st.markdown('<p class="sub-header">🔍 Filter Data</p>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Dropdown untuk memilih perusahaan
            all_companies = sorted(df_latest['SHARE_CODE'].unique())
            company_options = ["Semua Perusahaan"] + all_companies
            selected_company_filter = st.selectbox(
                "Pilih Perusahaan:",
                options=company_options,
                key="company_filter"
            )
        
        with col2:
            # Dropdown untuk memilih investor
            all_investors = sorted(df_latest['INVESTOR_NAME'].unique())
            investor_options = ["Semua Investor"] + all_investors
            selected_investor_filter = st.selectbox(
                "Pilih Investor:",
                options=investor_options,
                key="investor_filter"
            )
        
        # Filter berdasarkan pilihan
        display_df = df_latest.copy()
        
        if selected_company_filter != "Semua Perusahaan":
            display_df = display_df[display_df['SHARE_CODE'] == selected_company_filter]
        
        if selected_investor_filter != "Semua Investor":
            display_df = display_df[display_df['INVESTOR_NAME'] == selected_investor_filter]
        
        # Tabs untuk data terkini
        tab1, tab2, tab3 = st.tabs(["📋 Semua Data", "🏢 Top Perusahaan", "👥 Top Investor"])
        
        with tab1:
            st.subheader(f"Data ({len(display_df)} records)")
            st.dataframe(
                display_df[['SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 'PERCENTAGE', 
                           'INVESTOR_TYPE', 'LOCAL_FOREIGN']].sort_values('PERCENTAGE', ascending=False),
                use_container_width=True,
                height=500
            )
            
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Data",
                csv,
                f"ksei_data_{latest_date}.csv",
                "text/csv"
            )
        
        with tab2:
            top_companies = display_df.groupby(['SHARE_CODE', 'ISSUER_NAME']).agg({
                'PERCENTAGE': ['sum', 'count', 'max']
            }).round(2)
            top_companies.columns = ['TOTAL_%', 'JUMLAH_INVESTOR', 'MAKS_%']
            top_companies = top_companies.sort_values('TOTAL_%', ascending=False).head(20).reset_index()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.dataframe(top_companies[['SHARE_CODE', 'ISSUER_NAME', 'TOTAL_%', 'JUMLAH_INVESTOR']])
            
            with col2:
                fig = px.bar(
                    top_companies.head(10),
                    x='SHARE_CODE',
                    y='TOTAL_%',
                    color='JUMLAH_INVESTOR',
                    title="Top 10 Perusahaan",
                    labels={'TOTAL_%': 'Total Kepemilikan (%)', 'SHARE_CODE': 'Kode'}
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            top_investors = display_df.groupby(['INVESTOR_NAME']).agg({
                'PERCENTAGE': ['sum', 'count', 'max'],
                'SHARE_CODE': lambda x: ', '.join(x.head(3))
            }).round(2)
            top_investors.columns = ['TOTAL_%', 'JUMLAH_PERUSAHAAN', 'MAKS_%', 'SAMPLE_PERUSAHAAN']
            top_investors = top_investors.sort_values('TOTAL_%', ascending=False).head(20).reset_index()
            
            st.dataframe(top_investors)
    
    elif view_mode == "🔄 Perubahan":
        # ==================== PERUBAHAN ====================
        if df_previous is not None:
            st.markdown(f'<p class="sub-header">🔄 Perubahan Kepemilikan ({previous_date} → {latest_date})</p>', unsafe_allow_html=True)
            
            changes_df = compare_datasets(df_previous, df_latest, previous_date, latest_date)
            
            if not changes_df.empty:
                # Summary metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("Total Perubahan", len(changes_df))
                with col2:
                    added = len(changes_df[changes_df['TYPE'] == 'BERTAMBAH'])
                    st.metric("➕ Bertambah", added)
                with col3:
                    removed = len(changes_df[changes_df['TYPE'] == 'BERKURANG'])
                    st.metric("➖ Berkurang", removed)
                with col4:
                    changed = len(changes_df[changes_df['TYPE'] == 'BERUBAH'])
                    st.metric("🔄 Berubah", changed)
                with col5:
                    net = changes_df['CHANGE_%'].sum()
                    st.metric("💰 Net Change", f"{net:+.2f}%")
                
                st.divider()
                
                # Filter dengan dropdown
                st.markdown("### 🔍 Filter Perubahan")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Dropdown untuk memilih perusahaan
                    companies_in_changes = sorted(changes_df['SHARE_CODE'].unique())
                    company_options = ["Semua Perusahaan"] + companies_in_changes
                    selected_company_change = st.selectbox(
                        "Pilih Perusahaan:",
                        options=company_options,
                        key="company_change_filter"
                    )
                
                with col2:
                    # Dropdown untuk memilih investor
                    investors_in_changes = sorted(changes_df['INVESTOR_NAME'].unique())
                    investor_options = ["Semua Investor"] + investors_in_changes
                    selected_investor_change = st.selectbox(
                        "Pilih Investor:",
                        options=investor_options,
                        key="investor_change_filter"
                    )
                
                # Filter type
                type_filter = st.multiselect(
                    "Tipe Perubahan:",
                    options=['BERTAMBAH', 'BERKURANG', 'BERUBAH'],
                    default=['BERTAMBAH', 'BERKURANG', 'BERUBAH'],
                    format_func=lambda x: {
                        'BERTAMBAH': '➕ Bertambah',
                        'BERKURANG': '➖ Berkurang',
                        'BERUBAH': '🔄 Berubah'
                    }[x],
                    key="type_filter_change"
                )
                
                # Apply filters
                filtered_changes = changes_df.copy()
                
                if selected_company_change != "Semua Perusahaan":
                    filtered_changes = filtered_changes[filtered_changes['SHARE_CODE'] == selected_company_change]
                
                if selected_investor_change != "Semua Investor":
                    filtered_changes = filtered_changes[filtered_changes['INVESTOR_NAME'] == selected_investor_change]
                
                if type_filter:
                    filtered_changes = filtered_changes[filtered_changes['TYPE'].isin(type_filter)]
                
                # Tabs untuk perubahan
                tab1, tab2, tab3, tab4 = st.tabs(["📋 Semua", "➕ Bertambah", "➖ Berkurang", "🔄 Berubah"])
                
                with tab1:
                    st.dataframe(
                        filtered_changes.sort_values('CHANGE_%', ascending=False),
                        use_container_width=True
                    )
                    
                    csv = filtered_changes.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Data",
                        csv,
                        f"ksei_changes_{previous_date}_to_{latest_date}.csv",
                        "text/csv"
                    )
                
                with tab2:
                    added_df = filtered_changes[filtered_changes['TYPE'] == 'BERTAMBAH']
                    if not added_df.empty:
                        st.dataframe(
                            added_df[['SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 'NEW_%', 'INVESTOR_TYPE']]
                            .sort_values('NEW_%', ascending=False)
                        )
                    else:
                        st.info("Tidak ada investor baru")
                
                with tab3:
                    removed_df = filtered_changes[filtered_changes['TYPE'] == 'BERKURANG']
                    if not removed_df.empty:
                        st.dataframe(
                            removed_df[['SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 'OLD_%', 'INVESTOR_TYPE']]
                            .sort_values('OLD_%', ascending=False)
                        )
                    else:
                        st.info("Tidak ada investor yang keluar")
                
                with tab4:
                    changed_df = filtered_changes[filtered_changes['TYPE'] == 'BERUBAH']
                    if not changed_df.empty:
                        st.dataframe(
                            changed_df[['SHARE_CODE', 'INVESTOR_NAME', 'OLD_%', 'NEW_%', 'CHANGE_%']]
                            .sort_values('CHANGE_%', ascending=False)
                        )
                    else:
                        st.info("Tidak ada perubahan persentase")
            
            else:
                st.info("Tidak ada perubahan data antara kedua periode")
        else:
            st.warning("Diperlukan minimal 2 file untuk melihat perubahan")
    
    elif view_mode == "🏢 Perusahaan":
        # ==================== ANALISIS PERUSAHAAN ====================
        st.markdown('<p class="sub-header">🏢 Analisis Perusahaan</p>', unsafe_allow_html=True)
        
        # Dropdown untuk memilih perusahaan
        companies = sorted(df_latest['SHARE_CODE'].unique())
        
        # Tambahkan search box dengan selectbox
        selected_company = st.selectbox(
            "🔍 Cari dan Pilih Perusahaan:",
            options=companies,
            key="company_select",
            help="Ketik untuk mencari perusahaan"
        )
        
        if selected_company:
            # Data perusahaan terkini
            company_current = df_latest[df_latest['SHARE_CODE'] == selected_company].copy()
            company_name = company_current['ISSUER_NAME'].iloc[0]
            
            st.markdown(f"### {selected_company} - {company_name}")
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Investor", len(company_current))
            with col2:
                st.metric("Total Kepemilikan", f"{company_current['PERCENTAGE'].sum():.2f}%")
            with col3:
                st.metric("Rata-rata", f"{company_current['PERCENTAGE'].mean():.2f}%")
            with col4:
                st.metric("Terbesar", f"{company_current['PERCENTAGE'].max():.2f}%")
            
            # Daftar investor
            st.subheader(f"Daftar Investor")
            st.dataframe(
                company_current[['INVESTOR_NAME', 'PERCENTAGE', 'INVESTOR_TYPE', 'LOCAL_FOREIGN']]
                .sort_values('PERCENTAGE', ascending=False)
            )
            
            # Visualisasi
            fig = px.bar(
                company_current.head(15),
                x='INVESTOR_NAME',
                y='PERCENTAGE',
                title=f"Top Investors - {selected_company}",
                color='PERCENTAGE',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Jika ada data sebelumnya, tampilkan perubahan
            if df_previous is not None:
                company_previous = df_previous[df_previous['SHARE_CODE'] == selected_company]
                
                st.subheader("🔄 Perubahan Kepemilikan")
                
                # Gabungkan untuk perbandingan
                all_investors = set(company_previous['INVESTOR_NAME']) | set(company_current['INVESTOR_NAME'])
                
                changes = []
                for investor in all_investors:
                    old_data = company_previous[company_previous['INVESTOR_NAME'] == investor]
                    new_data = company_current[company_current['INVESTOR_NAME'] == investor]
                    
                    old_pct = old_data['PERCENTAGE'].iloc[0] if not old_data.empty else 0
                    new_pct = new_data['PERCENTAGE'].iloc[0] if not new_data.empty else 0
                    
                    if old_pct == 0:
                        status = "BARU"
                    elif new_pct == 0:
                        status = "KELUAR"
                    else:
                        status = "✓"
                    
                    changes.append({
                        'Investor': investor,
                        'Status': status,
                        f'{previous_date} (%)': round(old_pct, 2),
                        f'{latest_date} (%)': round(new_pct, 2),
                        'Perubahan': round(new_pct - old_pct, 2)
                    })
                
                changes_df = pd.DataFrame(changes)
                changes_df = changes_df[changes_df['Perubahan'] != 0]
                
                if not changes_df.empty:
                    st.dataframe(changes_df.sort_values('Perubahan', ascending=False))
    
    elif view_mode == "👥 Investor":
        # ==================== PROFIL INVESTOR ====================
        st.markdown('<p class="sub-header">👥 Profil Investor</p>', unsafe_allow_html=True)
        
        # Dropdown untuk memilih investor
        investors = sorted(df_latest['INVESTOR_NAME'].unique())
        
        selected_investor = st.selectbox(
            "🔍 Cari dan Pilih Investor:",
            options=investors,
            key="investor_select",
            help="Ketik untuk mencari investor"
        )
        
        if selected_investor:
            # Portfolio investor terkini
            investor_portfolio = df_latest[df_latest['INVESTOR_NAME'] == selected_investor].copy()
            
            st.markdown(f"### {selected_investor}")
            
            # Info investor
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Jumlah Perusahaan", len(investor_portfolio))
            with col2:
                st.metric("Total Kepemilikan", f"{investor_portfolio['PERCENTAGE'].sum():.2f}%")
            with col3:
                st.metric("Rata-rata per Company", f"{investor_portfolio['PERCENTAGE'].mean():.2f}%")
            
            # Tipe investor
            if 'INVESTOR_TYPE' in investor_portfolio.columns:
                tipe = investor_portfolio['INVESTOR_TYPE'].iloc[0]
                st.info(f"🏷️ Tipe Investor: {tipe}")
            
            # Portfolio
            st.subheader("📊 Portfolio Saat Ini")
            st.dataframe(
                investor_portfolio[['SHARE_CODE', 'ISSUER_NAME', 'PERCENTAGE']]
                .sort_values('PERCENTAGE', ascending=False)
            )
            
            # Visualisasi portfolio
            if len(investor_portfolio) > 1:
                fig = px.pie(
                    investor_portfolio,
                    values='PERCENTAGE',
                    names='SHARE_CODE',
                    title=f"Distribusi Portfolio - {selected_investor}"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Perubahan portfolio jika ada data sebelumnya
            if df_previous is not None:
                old_portfolio = df_previous[df_previous['INVESTOR_NAME'] == selected_investor]
                
                if not old_portfolio.empty:
                    st.subheader("🔄 Perubahan Portfolio")
                    
                    all_companies = set(old_portfolio['SHARE_CODE']) | set(investor_portfolio['SHARE_CODE'])
                    
                    changes = []
                    for company in all_companies:
                        old_data = old_portfolio[old_portfolio['SHARE_CODE'] == company]
                        new_data = investor_portfolio[investor_portfolio['SHARE_CODE'] == company]
                        
                        old_pct = old_data['PERCENTAGE'].iloc[0] if not old_data.empty else 0
                        new_pct = new_data['PERCENTAGE'].iloc[0] if not new_data.empty else 0
                        
                        if old_pct == 0:
                            aksi = "BELI BARU"
                        elif new_pct == 0:
                            aksi = "JUAL SEMUA"
                        elif new_pct > old_pct:
                            aksi = "TAMBAH"
                        elif new_pct < old_pct:
                            aksi = "KURANGI"
                        else:
                            aksi = "TETAP"
                        
                        changes.append({
                            'Perusahaan': company,
                            'Aksi': aksi,
                            f'{previous_date} (%)': round(old_pct, 2),
                            f'{latest_date} (%)': round(new_pct, 2),
                            'Perubahan': round(new_pct - old_pct, 2)
                        })
                    
                    changes_df = pd.DataFrame(changes)
                    changes_df = changes_df[changes_df['Perubahan'] != 0]
                    
                    if not changes_df.empty:
                        st.dataframe(changes_df.sort_values('Perubahan', ascending=False))

else:
    st.warning("Tidak ada data yang bisa ditampilkan. Pastikan folder `data/` berisi file CSV.")
    st.markdown("""
    ## Cara Penggunaan:
    1. Buat folder **`data/`** di direktori yang sama
    2. Letakkan file CSV dengan format: **`YYYY-MM-DD.csv`**
    3. Contoh: `2026-03-10.csv`, `2026-03-03.csv`
    """)

# Footer
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("📊 KSEI Dashboard v3.2")
with col2:
    if all_files:
        st.caption(f"📅 Data terbaru: {all_files[0][2].strftime('%d-%b-%Y')}")
with col3:
    st.caption("🎯 Fokus kepemilikan >1% | 🔍 Dropdown Search")