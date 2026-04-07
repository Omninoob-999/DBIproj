
param location string
param namePrefix string
param logAnalyticsId string

resource ai 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsId
  }
}
output connectionString string = ai.properties.ConnectionString
