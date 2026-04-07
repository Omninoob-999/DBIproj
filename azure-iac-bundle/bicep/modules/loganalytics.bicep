
param location string
param namePrefix string

resource la 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${namePrefix}-la'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}
output workspaceId string = la.id
output workspaceCustomerId string = la.properties.customerId
output workspaceSharedKey string = listKeys(la.id, '2020-08-01').primarySharedKey
