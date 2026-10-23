package com.videotranscriber.app.ui

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.VideoFile
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.videotranscriber.app.ExportFormat
import com.videotranscriber.app.LANGUAGES
import com.videotranscriber.app.Phase
import com.videotranscriber.app.TranscribeViewModel
import com.videotranscriber.app.TranscriptFormatter
import com.videotranscriber.app.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TranscribeScreen(vm: TranscribeViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbar.showSnackbar(it)
            vm.consumeMessage()
        }
    }

    val pickVideo = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            runCatching {
                context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            vm.setVideo(uri)
        }
    }
    val pickModel = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) vm.importModel(uri)
    }
    var pendingExport by rememberSaveable { mutableStateOf<ExportFormat?>(null) }
    val exportFile = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("*/*")) { uri: Uri? ->
        val format = pendingExport
        if (uri != null && format != null) vm.writeExport(uri, format)
        pendingExport = null
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Video Transcriber") }) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        val listState = rememberLazyListState()
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                ModelCard(
                    state = state,
                    onSelect = vm::selectModel,
                    onDownload = vm::downloadSelected,
                    onCancelDownload = vm::cancelDownload,
                    onDelete = vm::deleteSelectedModel,
                    onImport = { pickModel.launch(arrayOf("application/octet-stream", "*/*")) },
                )
            }
            item {
                VideoCard(
                    state = state,
                    onPick = { pickVideo.launch(arrayOf("video/*", "audio/*")) },
                    onLanguage = vm::setLanguage,
                    onTranslate = vm::setTranslate,
                )
            }
            item {
                RunCard(state = state, onStart = vm::transcribe, onCancel = vm::cancelTranscription)
            }
            if (state.segments.isNotEmpty()) {
                item {
                    TranscriptHeader(
                        state = state,
                        onToggleTimestamps = vm::setShowTimestamps,
                        onCopy = { clipboard.setText(AnnotatedString(vm.shareText())) },
                        onShare = {
                            val send = Intent(Intent.ACTION_SEND)
                                .setType("text/plain")
                                .putExtra(Intent.EXTRA_TEXT, vm.shareText())
                            context.startActivity(Intent.createChooser(send, "Share transcript"))
                        },
                        onExport = { format ->
                            pendingExport = format
                            exportFile.launch(vm.suggestedFileName(format))
                        },
                    )
                }
                itemsIndexed(state.segments) { _, segment ->
                    Row(verticalAlignment = Alignment.Top) {
                        if (state.showTimestamps) {
                            Text(
                                TranscriptFormatter.clock(segment.startMs),
                                style = MaterialTheme.typography.bodySmall,
                                fontFamily = FontFamily.Monospace,
                                color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.widthIn(min = 56.dp).padding(top = 2.dp),
                            )
                            Spacer(Modifier.width(8.dp))
                        }
                        SelectionContainer {
                            Text(segment.text, style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ModelCard(
    state: UiState,
    onSelect: (String) -> Unit,
    onDownload: () -> Unit,
    onCancelDownload: () -> Unit,
    onDelete: () -> Unit,
    onImport: () -> Unit,
) {
    val selected = state.selectedModel
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("1. Whisper model", style = MaterialTheme.typography.titleMedium)

            var expanded by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { if (!state.busy) expanded = it }) {
                OutlinedTextField(
                    value = selected?.let { it.label + if (it.available) "" else " (not downloaded)" } ?: "",
                    onValueChange = {},
                    readOnly = true,
                    enabled = !state.busy,
                    label = { Text("Model") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                    modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    state.models.forEach { m ->
                        DropdownMenuItem(
                            text = {
                                Column {
                                    Text(m.label + if (m.available) "  ✓" else "")
                                    Text(m.detail, style = MaterialTheme.typography.bodySmall)
                                }
                            },
                            onClick = {
                                onSelect(m.key)
                                expanded = false
                            },
                        )
                    }
                }
            }
            selected?.let { Text(it.detail, style = MaterialTheme.typography.bodySmall) }

            if (state.downloadingKey != null) {
                Text("Downloading… ${(state.downloadProgress * 100).toInt()}%")
                LinearProgressIndicator(progress = { state.downloadProgress }, modifier = Modifier.fillMaxWidth())
                TextButton(onClick = onCancelDownload) { Text("Cancel download") }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (selected != null && !selected.available && selected.downloadable != null) {
                        Button(onClick = onDownload) {
                            Icon(Icons.Default.Download, contentDescription = null)
                            Spacer(Modifier.width(6.dp))
                            Text("Download")
                        }
                    }
                    if (selected?.available == true) {
                        TextButton(onClick = onDelete, enabled = !state.busy) { Text("Delete") }
                    }
                    OutlinedButton(onClick = onImport, enabled = !state.busy) { Text("Import .bin") }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun VideoCard(
    state: UiState,
    onPick: () -> Unit,
    onLanguage: (String) -> Unit,
    onTranslate: (Boolean) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("2. Video", style = MaterialTheme.typography.titleMedium)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Button(onClick = onPick, enabled = !state.busy) {
                    Icon(Icons.Default.VideoFile, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text(if (state.videoUri == null) "Choose video" else "Change")
                }
                Spacer(Modifier.width(12.dp))
                Text(
                    state.videoName ?: "No file selected",
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            var expanded by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { if (!state.busy) expanded = it }) {
                OutlinedTextField(
                    value = LANGUAGES.firstOrNull { it.first == state.language }?.second ?: state.language,
                    onValueChange = {},
                    readOnly = true,
                    enabled = !state.busy,
                    label = { Text("Spoken language") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                    modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    LANGUAGES.forEach { (code, name) ->
                        DropdownMenuItem(text = { Text(name) }, onClick = {
                            onLanguage(code)
                            expanded = false
                        })
                    }
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Translate to English")
                    Text(
                        "Not supported by English-only or Turbo models",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Switch(checked = state.translate, onCheckedChange = onTranslate, enabled = !state.busy)
            }
        }
    }
}

@Composable
private fun RunCard(state: UiState, onStart: () -> Unit, onCancel: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (state.busy) {
                val (label, progress) = when (val p = state.phase) {
                    is Phase.ExtractingAudio -> "Extracting audio… ${(p.progress * 100).toInt()}%" to p.progress
                    is Phase.LoadingModel -> "Loading model…" to null
                    is Phase.Transcribing -> "Transcribing… ${(p.progress * 100).toInt()}%" to p.progress
                    else -> "" to null
                }
                Text(label)
                if (progress == null) {
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                } else {
                    LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
                }
                OutlinedButton(onClick = onCancel) { Text("Cancel") }
            } else {
                Button(onClick = onStart, enabled = state.canTranscribe, modifier = Modifier.fillMaxWidth()) {
                    Text("Transcribe")
                }
                when (val p = state.phase) {
                    is Phase.Done -> Text(
                        "Done in ${TranscriptFormatter.clock(p.seconds * 1000)} · ${state.segments.size} segments",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    is Phase.Failed -> Text(p.message, color = MaterialTheme.colorScheme.error)
                    else -> when {
                        state.selectedModel?.available != true -> Text(
                            "Download or import a model first.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        state.videoUri == null -> Text("Choose a video to transcribe.", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun TranscriptHeader(
    state: UiState,
    onToggleTimestamps: (Boolean) -> Unit,
    onCopy: () -> Unit,
    onShare: () -> Unit,
    onExport: (ExportFormat) -> Unit,
) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Transcript", style = MaterialTheme.typography.titleMedium)
                state.detectedLanguage?.takeIf { it.isNotEmpty() }?.let { code ->
                    val name = LANGUAGES.firstOrNull { it.first == code }?.second ?: code
                    Text("Language: $name", style = MaterialTheme.typography.bodySmall)
                }
            }
            IconButton(onClick = onCopy, enabled = !state.busy) {
                Icon(Icons.Default.ContentCopy, contentDescription = "Copy")
            }
            IconButton(onClick = onShare, enabled = !state.busy) {
                Icon(Icons.Default.Share, contentDescription = "Share")
            }
            var menu by remember { mutableStateOf(false) }
            IconButton(onClick = { menu = true }, enabled = !state.busy) {
                Icon(Icons.Default.Save, contentDescription = "Export")
            }
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                ExportFormat.entries.forEach { f ->
                    DropdownMenuItem(
                        text = { Text("Save as .${f.extension}") },
                        onClick = {
                            menu = false
                            onExport(f)
                        },
                    )
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Show timestamps", Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
            Switch(checked = state.showTimestamps, onCheckedChange = onToggleTimestamps)
        }
    }
}
