
param location string
param namePrefix string
param subnetId string

resource apim 'Microsoft.ApiManagement/service@2022-08-01' = {
  name: '${namePrefix}-apim'
  location: location
  sku: { name: 'Developer', capacity: 1 }
  properties: {
    publisherEmail: 'owner@example.com'
    publisherName: 'Owner'
    virtualNetworkConfiguration: { subnetResourceId: subnetId }
    virtualNetworkType: 'Internal'
  }
}
output gatewayHostname string = apim.properties.gatewayRegionalUrl
