from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt 
import scipy.stats as stats

###
# Section 1- Data Cleaning 
###

# Data path & Read parquet
base_dir = Path(__file__).resolve().parent
project_root = base_dir.parent

outliers_path = project_root / "dbt_project" / "data_exports" / "int_price_outliers.parquet"
instances_path = project_root / "dbt_project" / "data_exports" / "dim_instances.parquet"

outliers = pd.read_parquet(outliers_path)
instances = pd.read_parquet(instances_path)


# Data cleaninig- should be no issue since data transform in dbt stg
data_tables = {
    "outliers": outliers, 
    "instances": instances
}

for name, df in data_tables.items():
    print(f"Data checking for {name}")
    print(df.shape)           # check data sharp and data type
    print(df.info())
    print(df.isnull().sum())  # Check isnull
    print(df.duplicated().sum())
    print()


# Create new df- 'price' for downsizing outliers
column_select = ['sku', 'offer_term_code', 
                'instance_type', 
                'vcpu', 'memory_gb', 
                'operating_system', 
                'term_type', 'purchase_option', 'lease_year', 
                'pre_installed_sw', 'license_model',
                'region_code'
                ]

column_select_other = ['is_price_outlier']

numerical_select = ['price_per_hour']

column_select_update = column_select + column_select_other +  numerical_select

prices = outliers[column_select_update]

prices = prices.pivot_table(
    index = column_select + column_select_other, 
    values = numerical_select, 
    aggfunc = 'sum'
).reset_index()

print(prices.info())


# Pivot table check duplication
prices_check = prices.drop(columns = column_select_other)

duplicated_data = prices_check[prices_check.duplicated(subset = column_select)]
assert duplicated_data.empty, f"Found {len(duplicated_data)} duplication row(s) in df price_check"
print()


###
# Section 2- Higlight outliers (var% >= 50)
###

# Merge prices and instances
instances_keep = instances[['instance_sk', 'instance_type', 
                    'revised_processor_vendor', 'instance_family_category']]

prices_merge = pd.merge(prices, instances_keep, on='instance_type',how = 'left')
column_select_update.extend(['revised_processor_vendor', 'instance_family_category'])

prices_merge = prices_merge[column_select_update]


# Create 2 new columns - price_per_vcpu and price_per_memory
prices_merge['price_per_vcpu'] = prices_merge['price_per_hour'] / prices_merge['vcpu']
prices_merge['price_per_memory'] = prices_merge['price_per_hour'] / prices_merge['memory_gb']
print(prices_merge.info())
print()


# New columns- group_size for the frequency
group_cols = ['region_code', 'operating_system', 
              'term_type', 'purchase_option', 'lease_year',
              'instance_type', 'license_model', 'pre_installed_sw']

groupped_prices = prices_merge.groupby(group_cols)['price_per_hour']

prices_merge['group_size'] = groupped_prices.transform('size')
print(prices_merge.info())


# New columns- group_min, group_max, var 
for aggr in ['min', 'max']:
    prices_merge[f"group_{aggr}"] = groupped_prices.transform(aggr)

prices_merge['var_min_max'] = round(
    (prices_merge['group_max'] / prices_merge['group_min'] -1) * 100
    , 2)


# New columns- var_class
prices_merge['var_class'] = np.where(
    prices_merge['group_size'] == 1, 
    'no peer', 
    np.where(
        prices_merge['var_min_max'] < 50, 
        'accept', 
        'abnormal'
    )
) 


# Cross-check dbt and python result
cross_counts = pd.crosstab(
    index = prices_merge['is_price_outlier'],
    columns = prices_merge['var_class']
)

print(cross_counts)


###
# Section 3- Scattle chart
###

# Plot chart
ylabel_map = {
    'vcpu': 'vCPU Count',
    'memory_gb': 'Memory (GB)'
}

legend_values = {
    'no peer': 'orange', 
    'accept': 'green',
    'abnormal': 'black'
}

for col, y_title in ylabel_map.items():
    for item, color in legend_values.items():
        prices_chart = prices_merge.copy()
        prices_chart = prices_chart[prices_chart['var_class'] == item]

        x = prices_chart[col]
        y = prices_chart['price_per_hour']

        if item == 'abnormal':
            plt.scatter(x, y, color = color, alpha= 1, s= 15, label = item)
        else:
            plt.scatter(x, y, color = color, alpha= 0.4, label = item)

    plt.title(f'{y_title} x Hourly Rate')
    plt.xlabel(y_title)
    plt.ylabel('Hourly Rate (USD)')
    plt.legend()
    plt.show()


###
# Section 4- two-sample hypothesis test
###

# Filter basic case based on 4 columns
test_filter = {
    'operating_system'  : 'linux',
#    'term_type'         : 'OnDemand',
    'lease_year'        : 3, 
    'purchase_option'   : 'no upfront', 
    'pre_installed_sw'  : 'na',
    'license_model'   : 'no license required'
}

mask = pd.Series(True, index = prices_merge.index)
for col, val in test_filter.items():
    mask &= (prices_merge[col] == val)

price_test = prices_merge[mask]
print(price_test.info())


# Filter common instance_type (i.e. drop non-comparable instance_type)
region = {
    'ca-central-1'  : 'ca_central', 
    'us-east-1'     : 'us', 
    'ca-west-1'     :'ca_west'}

instance_dict = {}

for reg, reg_label in region.items():  
    price_region = price_test[price_test['region_code'] == reg]
    instance_dict[reg_label] = set(price_region['instance_type'])
    
instance_common = instance_dict['us'] & instance_dict['ca_central']

price_test = price_test[price_test['instance_type'].isin(instance_common)] 


# Split into 2 regioins- us & ca_central
price_vcpu = {}
price_mem = {}

for reg in region:  
    price_df = price_test[price_test['region_code'] == reg]
    price_vcpu[reg] = list(price_df['price_per_vcpu'])
   
    price_mem[reg] = list(price_df['price_per_memory'])

# T-test result
result_vcpu = stats.ttest_ind(price_vcpu['us-east-1'], 
                         price_vcpu['ca-central-1'], 
                         equal_var= False)

result_mem = stats.ttest_ind(price_mem['us-east-1'], 
                         price_mem['ca-central-1'], 
                         equal_var= False)

print('t-test of price_per_vcpu')
print(result_vcpu)
print()

print('t-test of price_per_memory')
print(result_mem)
