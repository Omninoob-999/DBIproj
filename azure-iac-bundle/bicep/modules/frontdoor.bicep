
param location string
param namePrefix string
param originHostname string

resource profile 'Microsoft.Cdn/profiles@2023-05-01' = {
  name: '${namePrefix}-afd'
  location: location
  sku: { name: 'Premium_AzureFrontDoor' }
}
resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2023-05-01' = {
  name: '${profile.name}/${namePrefix}-ep'
  location: location
  properties: { enabledState: 'Enabled' }
}
resource originGroup 'Microsoft.Cdn/profiles/originGroups@2023-05-01' = {
  name: '${profile.name}/${namePrefix}-og'
  location: location
  properties: {
    sessionAffinityState: 'Disabled'
    healthProbes: {
      probePath: '/health'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 60
    }
  }
}
resource origin 'Microsoft.Cdn/profiles/originGroups/origins@2023-05-01' = {
  name: '${profile.name}/${originGroup.name}/${namePrefix}-origin'
  properties: { hostName: originHostname, httpsPort: 443, priority: 1, weight: 1000, enabled: true }
}
