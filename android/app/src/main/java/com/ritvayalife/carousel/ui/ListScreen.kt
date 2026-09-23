package com.ritvayalife.carousel.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.ritvayalife.carousel.Carousel
import com.ritvayalife.carousel.SlideRenderer

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListScreen(
    carousels: List<Carousel>,
    renderer: SlideRenderer,
    onOpen: (String) -> Unit,
    onCreate: (String) -> Unit,
    onDuplicate: (Carousel) -> Unit,
    onDelete: (Carousel) -> Unit,
) {
    var showNew by remember { mutableStateOf(false) }
    var toDelete by remember { mutableStateOf<Carousel?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Ritvaya Carousels", color = Green) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Cream),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { showNew = true },
                icon = { Icon(Icons.Filled.Add, contentDescription = null) },
                text = { Text("New carousel") },
                containerColor = Green,
                contentColor = Color.White,
            )
        },
        containerColor = Cream,
    ) { padding ->
        if (carousels.isEmpty()) {
            Box(Modifier.fillMaxSize().padding(padding).padding(32.dp), contentAlignment = Alignment.Center) {
                Text("No carousels yet. Tap “New carousel” and type a topic.", color = Gray)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(
                    start = 16.dp,
                    end = 16.dp,
                    top = padding.calculateTopPadding() + 8.dp,
                    bottom = padding.calculateBottomPadding() + 96.dp,
                ),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(carousels, key = { it.slug }) { c ->
                    CarouselRow(
                        carousel = c,
                        renderer = renderer,
                        onOpen = { onOpen(c.slug) },
                        onDuplicate = { onDuplicate(c) },
                        onDelete = { toDelete = c },
                    )
                }
            }
        }
    }

    if (showNew) {
        NewCarouselDialog(
            onDismiss = { showNew = false },
            onCreate = { showNew = false; onCreate(it) },
        )
    }

    toDelete?.let { c ->
        AlertDialog(
            onDismissRequest = { toDelete = null },
            title = { Text("Delete carousel?") },
            text = { Text("“${c.title}” will be removed from the app. Images already saved to your gallery stay there.") },
            confirmButton = { TextButton(onClick = { onDelete(c); toDelete = null }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { toDelete = null }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun CarouselRow(
    carousel: Carousel,
    renderer: SlideRenderer,
    onOpen: () -> Unit,
    onDuplicate: () -> Unit,
    onDelete: () -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    Card(
        onClick = onOpen,
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFBF8F2)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            SlidePreview(carousel, 0, renderer, Modifier.width(72.dp), scale = .4f)
            Column(
                Modifier
                    .weight(1f)
                    .padding(horizontal = 14.dp),
            ) {
                Text(
                    carousel.title,
                    style = MaterialTheme.typography.titleMedium,
                    color = Green,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "${carousel.slides.size} slides · ${carousel.label}",
                    style = MaterialTheme.typography.bodySmall,
                    color = Gray,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Box {
                IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, contentDescription = "More") }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Duplicate") }, onClick = { menu = false; onDuplicate() })
                    DropdownMenuItem(text = { Text("Delete") }, onClick = { menu = false; onDelete() })
                }
            }
        }
    }
}

@Composable
private fun NewCarouselDialog(onDismiss: () -> Unit, onCreate: (String) -> Unit) {
    var topic by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New carousel") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "You'll get an 8-slide outline (hook → problem → meaning → how it works → steps → insight → action → save/share) to fill in.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Gray,
                )
                OutlinedTextField(
                    value = topic,
                    onValueChange = { topic = it },
                    label = { Text("Topic") },
                    placeholder = { Text("e.g. Oil pulling") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onCreate(topic.trim()) }, enabled = topic.isNotBlank()) { Text("Create") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
