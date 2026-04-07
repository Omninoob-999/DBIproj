
param projectName string
param location string = 'southeastasia'
param containerImage string
param openAiResourceId string

var namePrefix = toLower('${projectName}')

module vnet 'modules/vnet.bicep' = {
  name: '${namePrefix}-vnet'
  params: { location: location, namePrefix: namePrefix }
}
module acr 'modules/acr.bicep' = {
  name: '${namePrefix}-acr'
  params: { location: location, namePrefix: namePrefix, sku: 'Basic' }
}
module la 'modules/loganalytics.bicep' = {
  name: '${namePrefix}-la'
  params: { location: location, namePrefix: namePrefix }
}
module ai 'modules/appinsights.bicep' = {
  name: '${namePrefix}-ai'
  params: { location: location, namePrefix: namePrefix, logAnalyticsId: la.outputs.workspaceId }
}
module kv 'modules/kv.bicep' = {
  name: '${namePrefix}-kv'
  params: { location: location, namePrefix: namePrefix }
}
module caEnv 'modules/containerapps-env.bicep' = {
  name: '${namePrefix}-env'
  params: {
    location: location
    namePrefix: namePrefix
    logAnalyticsCustomerId: la.outputs.workspaceCustomerId
    logAnalyticsSharedKey: la.outputs.workspaceSharedKey
  }
}
module caApp 'modules/containerapp.bicep' = {
  name: '${namePrefix}-app'
  params: {
    location: location
    namePrefix: namePrefix
    envId: caEnv.outputs.envId
    image: containerImage
    appInsightsConnectionString: ai.outputs.connectionString
  }
}
module apim 'modules/apim.bicep' = {
  name: '${namePrefix}-apim'
  params: { location: location, namePrefix: namePrefix, subnetId: vnet.outputs.apimSubnetId }
}
module aoaiPe 'modules/openai-private-endpoint.bicep' = {
  name: '${namePrefix}-aoai-pe'
  params: {
    location: location
    namePrefix: namePrefix
    vnetId: vnet.outputs.vnetId
    peSubnetId: vnet.outputs.privateEndpointSubnetId
    targetResourceId: openAiResourceId
    groupId: 'openai'
  }
}
module afd 'modules/frontdoor.bicep' = {
  name: '${namePrefix}-afd'
  params: { location: location, namePrefix: namePrefix, originHostname: apim.outputs.gatewayHostname }
}
