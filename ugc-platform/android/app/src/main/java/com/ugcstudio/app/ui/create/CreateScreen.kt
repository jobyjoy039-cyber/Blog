package com.ugcstudio.app.ui.create

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.ugcstudio.app.domain.model.AdFramework
import com.ugcstudio.app.domain.model.AdPlatform
import com.ugcstudio.app.domain.model.KITTEN_VOICES
import com.ugcstudio.app.domain.model.Resolution

@Composable
fun CreateScreen(sharedUrl: String?, onCreated: (String) -> Unit, vm: CreateViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    LaunchedEffect(sharedUrl) { sharedUrl?.let(vm::onSharedUrl) }
    LaunchedEffect(Unit) { vm.created.collect(onCreated) }
    CreateContent(state, vm::update, vm::addImages, vm::removeImage, vm::submit)
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun CreateContent(
    state: CreateState,
    update: (CreateState.() -> CreateState) -> Unit,
    addImages: (List<String>) -> Unit,
    removeImage: (String) -> Unit,
    submit: () -> Unit,
) {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(6)) { uris ->
        addImages(uris.map { it.toString() })
    }
    Column(
        Modifier.verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("New ad", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(
            "Paste a product link, or share one to this app from any store. We'll pull the details, write the script, voice it and edit the video.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            SourceMode.entries.forEachIndexed { i, mode ->
                SegmentedButton(
                    selected = state.mode == mode,
                    onClick = { update { copy(mode = mode) } },
                    shape = SegmentedButtonDefaults.itemShape(i, SourceMode.entries.size),
                ) { Text(if (mode == SourceMode.LINK) "Product link" else "Enter details") }
            }
        }

        if (state.mode == SourceMode.LINK) {
            OutlinedTextField(
                value = state.url, onValueChange = { update { copy(url = it) } },
                label = { Text("Product URL") }, placeholder = { Text("https://store.com/products/…") },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                supportingText = { Text("Shopify, WooCommerce and most stores work. Marketplaces that block bots need 'Enter details'.") },
            )
        } else {
            OutlinedTextField(state.title, { v -> update { copy(title = v) } }, Modifier.fillMaxWidth(), label = { Text("Product name") }, singleLine = true)
            OutlinedTextField(state.price, { v -> update { copy(price = v) } }, Modifier.fillMaxWidth(), label = { Text("Price (optional)") }, singleLine = true)
            OutlinedTextField(state.description, { v -> update { copy(description = v) } }, Modifier.fillMaxWidth(), label = { Text("What it does") }, minLines = 2)
            OutlinedTextField(state.features, { v -> update { copy(features = v) } }, Modifier.fillMaxWidth(), label = { Text("Key features, one per line") }, minLines = 3)
            Text("Product photos (up to 6)", style = MaterialTheme.typography.labelLarge)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                state.images.forEach { uri ->
                    Box {
                        AsyncImage(uri, null, Modifier.size(84.dp).clip(RoundedCornerShape(12.dp)), contentScale = ContentScale.Crop)
                        IconButton(onClick = { removeImage(uri) }, modifier = Modifier.align(Alignment.TopEnd).size(28.dp)) {
                            Icon(Icons.Default.Close, "Remove")
                        }
                    }
                }
                if (state.images.size < 6) {
                    OutlinedButton(
                        onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                        modifier = Modifier.size(84.dp), shape = RoundedCornerShape(12.dp),
                    ) { Icon(Icons.Default.AddPhotoAlternate, "Add photos") }
                }
            }
        }

        Text("Platform", style = MaterialTheme.typography.titleSmall)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            AdPlatform.entries.forEach { p ->
                FilterChip(selected = state.platform == p, onClick = { update { copy(platform = p) } },
                    label = { Text("${p.label} · ${p.aspect}") })
            }
        }

        var open by remember { mutableStateOf(false) }
        ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
            OutlinedTextField(
                value = state.framework.label, onValueChange = {}, readOnly = true,
                label = { Text("Script framework") }, supportingText = { Text(state.framework.blurb) },
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
                modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
            )
            ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                AdFramework.entries.forEach { f ->
                    DropdownMenuItem(text = { Text(f.label) }, onClick = { update { copy(framework = f) }; open = false })
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Length: ${state.seconds}s", style = MaterialTheme.typography.titleSmall)
                Slider(
                    value = state.seconds.toFloat(), onValueChange = { update { copy(seconds = it.toInt()) } },
                    valueRange = 8f..60f, steps = 51,
                )
                Text("Voice", style = MaterialTheme.typography.titleSmall)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    KITTEN_VOICES.forEach { v ->
                        FilterChip(selected = state.voice == v, onClick = { update { copy(voice = v) } }, label = { Text(v) })
                    }
                }
                Text("Resolution", style = MaterialTheme.typography.titleSmall)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Resolution.entries.forEach { r ->
                        FilterChip(selected = state.resolution == r, onClick = { update { copy(resolution = r) } }, label = { Text(r.wire) })
                    }
                }
            }
        }

        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        Button(onClick = submit, enabled = !state.submitting, modifier = Modifier.fillMaxWidth().height(52.dp)) {
            if (state.submitting) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            else {
                Icon(Icons.Default.AutoAwesome, null)
                Spacer(Modifier.size(8.dp))
                Text("Create ad")
            }
        }
    }
}
