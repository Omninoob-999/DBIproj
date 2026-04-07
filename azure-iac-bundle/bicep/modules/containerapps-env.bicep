
param location string
param namePrefix string
param logAnalyticsCustomerId string
param logAnalyticsSharedKey string

resource env 'Microsoft.App/managedEnvironments@2024-02-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
  }
}
output envId string = env.id
