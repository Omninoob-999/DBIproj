
param location string
param namePrefix string

resource kv 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: '${namePrefix}-kv'
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { name: 'standard', family: 'A' }
    enableRbacAuthorization: true
    enablePurgeProtection: true
  }
}
output kvId string = kv.id
output kvName string = kv.name
