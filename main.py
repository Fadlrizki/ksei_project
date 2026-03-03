import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import glob
import os

# Page config
st.set_page_config(
    page_title="KSEI Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title
st.title("📊 KSEI Shareholder Dashboard ( >1% Ownership )")

# Initialize session state untuk tab
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 0

# Fungsi untuk mendapatkan file terbaru
@st.cache_data(ttl=60)
def get_latest_file(data_dir="data"):
    """Mengambil file CSV terbaru dari folder data"""
    Path(data_dir).mkdir(exist_ok=True)
    
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        return None, None
    
    # Sort by modified time (terbaru pertama)
    csv_files.sort(key=os.path.getmtime, reverse=True)
    
    # Ambil file terbaru
    latest_file = csv_files[0]
    
    # Load data - skip baris yang bermasalah
    df = pd.read_csv(latest_file, header=None, skiprows=1)
    
    # Set column names
    df.columns = ['DATE', 'SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 
                  'INVESTOR_TYPE', 'LOCAL_FOREIGN', 'NATIONALITY', 'DOMICILE',
                  'HOLDINGS_SCRIPLESS', 'HOLDINGS_SCRIP', 'TOTAL_HOLDING_SHARES', 
                  'PERCENTAGE', 'EXTRA']
    
    # Hapus kolom EXTRA jika ada
    if 'EXTRA' in df.columns:
        df = df.drop('EXTRA', axis=1)
    
    # Hapus baris yang mengandung header (yang masih ada teks)
    df = df[~df['SHARE_CODE'].astype(str).str.contains('SHARE_CODE', na=False)]
    df = df[~df['PERCENTAGE'].astype(str).str.contains('PERCENTAGE', na=False)]
    
    # Convert DATE
    df['DATE'] = pd.to_datetime(df['DATE'], format='%d-%b-%Y', errors='coerce')
    
    # Convert PERCENTAGE (handle comma as decimal)
    if 'PERCENTAGE' in df.columns:
        # Bersihkan persentase: hapus tanda kutip, ganti koma dengan titik
        df['PERCENTAGE'] = df['PERCENTAGE'].astype(str).str.replace('"', '').str.replace(',', '.').str.strip()
        # Convert ke float, yang tidak bisa di-convert jadi NaN
        df['PERCENTAGE'] = pd.to_numeric(df['PERCENTAGE'], errors='coerce')
    
    # Convert numeric columns
    numeric_cols = ['HOLDINGS_SCRIPLESS', 'HOLDINGS_SCRIP', 'TOTAL_HOLDING_SHARES']
    for col in numeric_cols:
        if col in df.columns:
            # Bersihkan angka: hapus titik dan koma
            df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Hapus baris dengan SHARE_CODE kosong atau NaN
    df = df.dropna(subset=['SHARE_CODE'])
    
    # Reset index
    df = df.reset_index(drop=True)
    
    return df, os.path.basename(latest_file)

# Load data
df, filename = get_latest_file()

# Sidebar
with st.sidebar:
    st.header("📁 Data Info")
    
    if df is not None and not df.empty:
        st.success(f"File: {filename}")
        
        # Tampilkan info
        st.metric("Total Records", f"{len(df):,}")
        st.metric("Unique Issuers", df['SHARE_CODE'].nunique())
        st.metric("Unique Investors", df['INVESTOR_NAME'].nunique())
        
        if 'DATE' in df.columns and not df['DATE'].isna().all():
            latest_date = df['DATE'].iloc[0]
            # Convert to string for display
            st.metric("Report Date", latest_date.strftime('%d-%b-%Y'))
        
        # Filter options
        st.divider()
        st.header("🔍 Filters")
        
        # Search box
        search = st.text_input("Search Company/Investor", "", key="search_input")
        
        # Min percentage filter
        min_percent = st.slider("Min Percentage (%)", 0.0, 100.0, 0.0, key="min_percent_slider")
        
        # Local/Foreign filter
        if 'LOCAL_FOREIGN' in df.columns:
            local_options = ['All', 'L (Lokal)', 'A (Asing)', 'Unknown']
            selected_local = st.selectbox("Local/Foreign", local_options, key="local_select")
        else:
            selected_local = 'All'
        
    else:
        st.warning("Tidak ada file CSV di folder `data/`")
        st.info("Letakkan file CSV hasil konversi di folder `data/`")

# Main content
if df is not None and not df.empty:
    # Apply filters
    filtered_df = df.copy()
    
    if search:
        filtered_df = filtered_df[
            filtered_df['SHARE_CODE'].astype(str).str.contains(search.upper(), na=False) |
            filtered_df['ISSUER_NAME'].astype(str).str.contains(search.upper(), na=False) |
            filtered_df['INVESTOR_NAME'].astype(str).str.contains(search.upper(), na=False)
        ]
    
    filtered_df = filtered_df[filtered_df['PERCENTAGE'] >= min_percent]
    
    if selected_local != 'All':
        if selected_local == 'L (Lokal)':
            filtered_df = filtered_df[filtered_df['LOCAL_FOREIGN'] == 'L']
        elif selected_local == 'A (Asing)':
            filtered_df = filtered_df[filtered_df['LOCAL_FOREIGN'] == 'A']
        elif selected_local == 'Unknown':
            filtered_df = filtered_df[filtered_df['LOCAL_FOREIGN'].isna()]
    
    # Tabs with session state
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Overview", 
        "🏢 Per Company",
        "👥 Per Investor",
        "📋 Raw Data"
    ])
    
    with tab1:
        st.session_state.active_tab = 0
        st.header("Market Overview")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Companies", filtered_df['SHARE_CODE'].nunique())
        with col2:
            st.metric("Total Investors", filtered_df['INVESTOR_NAME'].nunique())
        with col3:
            st.metric("Avg %", f"{filtered_df['PERCENTAGE'].mean():.2f}%")
        with col4:
            st.metric("Total %", f"{filtered_df['PERCENTAGE'].sum():.2f}%")
        
        # Top 20 largest shareholders
        st.subheader("🏆 Top 20 Largest Shareholders")
        top_holders = filtered_df.nlargest(20, 'PERCENTAGE')[
            ['SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 'PERCENTAGE']
        ]
        
        fig = px.bar(
            top_holders,
            x='PERCENTAGE',
            y='INVESTOR_NAME',
            color='SHARE_CODE',
            orientation='h',
            title="Top 20 Shareholders by Percentage",
            labels={'PERCENTAGE': 'Percentage (%)', 'INVESTOR_NAME': 'Shareholder'}
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=600)
        st.plotly_chart(fig, use_container_width=True)
        
        # Local vs Foreign
        if 'LOCAL_FOREIGN' in filtered_df.columns:
            st.subheader("🌏 Local vs Foreign")
            col1, col2 = st.columns(2)
            
            with col1:
                lf_count = filtered_df['LOCAL_FOREIGN'].value_counts()
                if not lf_count.empty:
                    fig = px.pie(
                        values=lf_count.values,
                        names=lf_count.index,
                        title="By Number of Holders",
                        color_discrete_map={'L': 'green', 'A': 'orange'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                lf_sum = filtered_df.groupby('LOCAL_FOREIGN')['PERCENTAGE'].sum()
                if not lf_sum.empty:
                    fig = px.pie(
                        values=lf_sum.values,
                        names=lf_sum.index,
                        title="By Total Percentage",
                        color_discrete_map={'L': 'green', 'A': 'orange'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # Top companies by total ownership
        st.subheader("🏢 Top 10 Companies by Total Ownership")
        top_companies = filtered_df.groupby(['SHARE_CODE', 'ISSUER_NAME']).agg({
            'PERCENTAGE': 'sum',
            'INVESTOR_NAME': 'count'
        }).rename(columns={'PERCENTAGE': 'TOTAL_%', 'INVESTOR_NAME': 'NUM_HOLDERS'}).round(2)
        top_companies = top_companies.sort_values('TOTAL_%', ascending=False).head(10).reset_index()
        
        if not top_companies.empty:
            fig = px.bar(
                top_companies,
                x='SHARE_CODE',
                y='TOTAL_%',
                color='NUM_HOLDERS',
                title="Top 10 Companies by Total Shareholder Percentage",
                labels={'TOTAL_%': 'Total Percentage (%)', 'SHARE_CODE': 'Company Code'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.session_state.active_tab = 1
        st.header("Per Company Analysis")
        
        # Company selector
        companies = sorted(filtered_df['SHARE_CODE'].unique())
        selected_company = st.selectbox("Select Company", companies, key="company_select")
        
        if selected_company:
            company_data = filtered_df[filtered_df['SHARE_CODE'] == selected_company].copy()
            company_name = company_data['ISSUER_NAME'].iloc[0]
            
            st.subheader(f"{selected_company} - {company_name}")
            
            # Company metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Shareholders", len(company_data))
            with col2:
                st.metric("Total Ownership %", f"{company_data['PERCENTAGE'].sum():.2f}%")
            with col3:
                st.metric("Largest Holder", f"{company_data['PERCENTAGE'].max():.2f}%")
            with col4:
                st.metric("Avg % per Holder", f"{company_data['PERCENTAGE'].mean():.2f}%")
            
            # Shareholders table
            st.subheader("Shareholders")
            display_cols = ['INVESTOR_NAME', 'PERCENTAGE', 'TOTAL_HOLDING_SHARES', 
                           'INVESTOR_TYPE', 'LOCAL_FOREIGN', 'NATIONALITY']
            available_cols = [col for col in display_cols if col in company_data.columns]
            
            company_display = company_data[available_cols].sort_values('PERCENTAGE', ascending=False)
            company_display['PERCENTAGE'] = company_display['PERCENTAGE'].round(2)
            
            st.dataframe(company_display, use_container_width=True)
            
            # Bar chart
            fig = px.bar(
                company_display.head(15),
                x='PERCENTAGE',
                y='INVESTOR_NAME',
                orientation='h',
                title=f"Top Shareholders - {selected_company}",
                color='PERCENTAGE',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.session_state.active_tab = 2
        st.header("Per Investor Analysis")
        
        # Investor selector
        investors = sorted(filtered_df['INVESTOR_NAME'].unique())
        selected_investor = st.selectbox("Select Investor", investors, key="investor_select")
        
        if selected_investor:
            investor_data = filtered_df[filtered_df['INVESTOR_NAME'] == selected_investor].copy()
            
            st.subheader(f"Investor: {selected_investor}")
            
            # Investor metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Companies Invested", len(investor_data))
            with col2:
                st.metric("Total Ownership %", f"{investor_data['PERCENTAGE'].sum():.2f}%")
            with col3:
                st.metric("Largest Holding", f"{investor_data['PERCENTAGE'].max():.2f}%")
            
            # Portfolio
            st.subheader("Portfolio")
            portfolio = investor_data[['SHARE_CODE', 'ISSUER_NAME', 'PERCENTAGE', 'TOTAL_HOLDING_SHARES']]
            portfolio = portfolio.sort_values('PERCENTAGE', ascending=False)
            portfolio['PERCENTAGE'] = portfolio['PERCENTAGE'].round(2)
            
            st.dataframe(portfolio, use_container_width=True)
            
            # Pie chart
            if not portfolio.empty:
                fig = px.pie(
                    portfolio,
                    values='PERCENTAGE',
                    names='SHARE_CODE',
                    title=f"{selected_investor} - Portfolio Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.session_state.active_tab = 3
        st.header("Raw Data")
        
        # Filters for raw data
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_company = st.multiselect(
                "Filter by Company",
                options=sorted(filtered_df['SHARE_CODE'].unique()),
                key="filter_company_multiselect"
            )
        with col2:
            if 'LOCAL_FOREIGN' in filtered_df.columns:
                filter_type = st.multiselect(
                    "Filter by Type",
                    options=filtered_df['LOCAL_FOREIGN'].dropna().unique(),
                    key="filter_type_multiselect"
                )
            else:
                filter_type = []
        with col3:
            min_percent_raw = st.number_input("Min Percentage", 0.0, 100.0, 0.0, key="min_percent_raw_input")
        
        # Apply filters
        raw_df = filtered_df.copy()
        if filter_company:
            raw_df = raw_df[raw_df['SHARE_CODE'].isin(filter_company)]
        if filter_type:
            raw_df = raw_df[raw_df['LOCAL_FOREIGN'].isin(filter_type)]
        raw_df = raw_df[raw_df['PERCENTAGE'] >= min_percent_raw]
        
        # Display
        st.write(f"Showing {len(raw_df)} records")
        
        # Format for display
        display_df = raw_df.copy()
        if 'DATE' in display_df.columns:
            display_df['DATE'] = display_df['DATE'].dt.strftime('%d-%b-%Y')
        display_df['PERCENTAGE'] = display_df['PERCENTAGE'].round(2)
        
        st.dataframe(display_df, use_container_width=True)
        
        # Download button
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download as CSV",
            csv,
            "ksei_data.csv",
            "text/csv"
        )

else:
    st.info("📁 Letakkan file CSV di folder `data/`")
    st.markdown("""
    ## Cara Penggunaan:
    1. Buat folder `data/` di direktori yang sama dengan `main.py`
    2. Letakkan file CSV hasil konversi dari PDF KSEI di folder `data/`
    3. Refresh halaman untuk melihat data terbaru
    
    Dashboard akan otomatis mengambil **file terbaru** berdasarkan waktu modifikasi.
    """)

# Footer
st.divider()
st.caption("Data dibaca dari folder `data/` - File CSV terbaru")