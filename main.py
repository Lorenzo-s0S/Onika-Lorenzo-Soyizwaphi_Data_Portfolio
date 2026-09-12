import pandas as pd 

df_cpi= pd.read_csv(r"C:\Users\user\OneDrive\Desktop\Portfolio Project 1\Resources\ZAFCP030000IXOBQ.csv")
r_fce = pd.read_csv(r"C:\Users\user\OneDrive\Desktop\Portfolio Project 1\Resources\Real Final Consumption Expenditure.csv")

print("CPI Data")
#print(CPI.head())
#print(CPI.tail())
#print(CPI.describe())
#print(CPI.shape)
#print(df_cpi.columns.to_list())
df_cpi = df_cpi.iloc[:, 0].str.split(';', expand=True)##seperate the two columns and names
df_cpi.columns = ['observation_date', 'cpi_cf']
print(df_cpi.head())

##Changing the datatypes of the 2 columns
df_cpi['observation_date'] = pd.to_datetime(df_cpi['observation_date'],)
df_cpi['cpi_cf'] = pd.to_numeric(df_cpi['cpi_cf'], errors='coerce')

##Converting Dates format
#df_cpi['observation_date'] = df_cpi['observation_date'].dt.strftime('%Y/%m/%d')

print(df_cpi.dtypes)
print(df_cpi.tail())

print("real consumption expenditure data")
print(r_fce.head())
print(r_fce.describe())
print(r_fce.dtypes)

r_fce = r_fce.iloc[:, 0].str.split(';', expand=True)##seperate the two columns and names
r_fce.columns = ['observation_date', 'real_fce']

print(r_fce.head())

##Changing the datatypes of the 2 columns
r_fce['observation_date'] = pd.to_datetime(r_fce['observation_date'])
r_fce['real_fce'] = pd.to_numeric(r_fce['real_fce'], errors='coerce')


print(df_cpi.loc[df_cpi.observation_date >= '2008/01/01'])
print(r_fce.loc[r_fce.observation_date >= '2008/01/01'])


##Merging the datasets from 2008 down.
d_consol = pd.merge(df_cpi, r_fce, on='observation_date', how='inner')

d_consol = d_consol.loc[d_consol['observation_date'] >= '2008-01-01']

print(d_consol.tail())
print(d_consol.shape)
print(d_consol.columns)

d_consol.to_csv('CPI_RFCE.csv', index= False)