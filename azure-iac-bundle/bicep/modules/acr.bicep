
param location string
param namePrefix string
param sku string = 'Basic'

resource acr 'Microsoft.ContainerRegistry/registries@2023-08-01-preview' = {
  name: '${namePrefix}acr'
  location: location
  sku: { name: sku }
  properties: { adminUserEnabled: false }
}
output loginServer string = acr.properties.loginServer
output acrId string = acr.id
