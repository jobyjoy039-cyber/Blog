package com.ugcstudio.app.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun SettingsScreen(vm: SettingsViewModel = hiltViewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    Column(
        Modifier.verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Settings", style = MaterialTheme.typography.headlineMedium)
        OutlinedTextField(s.baseUrl, { vm.edit(url = it) }, Modifier.fillMaxWidth(), label = { Text("Studio server URL") }, singleLine = true)
        OutlinedTextField(
            s.apiKey, { vm.edit(key = it) }, Modifier.fillMaxWidth(), label = { Text("API key") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            supportingText = { Text("Stored encrypted with an Android Keystore key.") },
        )
        Button(onClick = vm::saveAndTest, enabled = !s.busy) { Text("Save and test") }
        s.status?.let { Text(it, color = if (s.ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error) }

        if (s.plugins.isNotEmpty()) {
            Text("AI modules", style = MaterialTheme.typography.titleMedium)
            Text("Pick which module handles each step. Others stay as automatic fallbacks.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            s.plugins.groupBy { it.capability }.forEach { (capability, plugins) ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(capability.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.titleSmall)
                        val anyPreferred = plugins.any { it.preferred }
                        plugins.forEachIndexed { i, p ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                RadioButton(
                                    selected = p.preferred || (!anyPreferred && i == plugins.indexOfFirst { it.available }),
                                    onClick = { vm.prefer(p) }, enabled = p.available,
                                )
                                Column {
                                    Text(p.name + if (!p.commercialOk) "  (non-commercial)" else "")
                                    Text(if (p.available) p.description else p.reason,
                                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
