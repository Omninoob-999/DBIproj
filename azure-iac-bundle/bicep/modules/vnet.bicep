
param location string
param namePrefix string

var vnetName = '${namePrefix}-vnet'

resource vnet 'Microsoft.Network/virtualNetworks@2022-07-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: { addressPrefixes: [ '10.20.0.0/16' ] }
    subnets: [
      {
        name: 'apim-subnet'
        properties: {
          addressPrefix: '10.20.1.0/24'
          delegations: [
            {
              name: 'apimdelegation'
              properties: { serviceName: 'Microsoft.ApiManagement/service' }
            }
          ]
        }
      }
      {
        name: 'pe-subnet'
        properties: {
          addressPrefix: '10.20.2.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output apimSubnetId string = vnet.properties.subnets[0].id
output privateEndpointSubnetId string = vnet.properties.subnets[1].id
