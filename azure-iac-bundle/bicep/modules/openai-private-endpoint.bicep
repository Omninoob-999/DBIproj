
param location string
param namePrefix string
param vnetId string
param peSubnetId string
param targetResourceId string
param groupId string = 'openai'

resource pe 'Microsoft.Network/privateEndpoints@2022-09-01' = {
  name: '${namePrefix}-aoai-pe'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      {
        name: '${namePrefix}-aoai-pls'
        properties: {
          privateLinkServiceId: targetResourceId
          groupIds: [ groupId ]
          requestMessage: 'Private access to Azure OpenAI'
        }
      }
    ]
  }
}
