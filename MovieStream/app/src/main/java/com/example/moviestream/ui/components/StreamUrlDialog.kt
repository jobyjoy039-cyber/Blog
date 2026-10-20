package com.example.moviestream.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType

/** Lets the user play any stream they have rights to: MP4, MKV, WebM, HLS (.m3u8) or DASH (.mpd). */
@Composable
fun StreamUrlDialog(onDismiss: () -> Unit, onPlay: (String) -> Unit) {
    var url by rememberSaveable { mutableStateOf("") }
    val valid = url.trim().let { it.startsWith("https://") || it.startsWith("http://") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Play a stream URL") },
        text = {
            Column {
                Text(
                    "Paste a link to a video you have the right to watch (MP4, HLS .m3u8 or DASH .mpd).",
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    singleLine = true,
                    placeholder = { Text("https://…") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
                )
            }
        },
        confirmButton = {
            TextButton(enabled = valid, onClick = { onPlay(url.trim()) }) { Text("Play") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
