package com.ritvayalife.carousel.ui

import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.ritvayalife.carousel.Carousel
import com.ritvayalife.carousel.Exporter
import com.ritvayalife.carousel.Field
import com.ritvayalife.carousel.Slide
import com.ritvayalife.carousel.SlideRenderer
import com.ritvayalife.carousel.Templates
import com.ritvayalife.carousel.get
import com.ritvayalife.carousel.set
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EditorScreen(
    initial: Carousel,
    renderer: SlideRenderer,
    onSave: (Carousel) -> Unit,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var carousel by remember { mutableStateOf(initial) }
    // Bumped whenever slides are added, removed or moved, so field editors reset.
    var structure by remember { mutableIntStateOf(0) }
    var busy by remember { mutableStateOf(false) }
    var exported by remember { mutableStateOf<List<Uri>?>(null) }
    val pager = rememberPagerState { carousel.slides.size }
    val current = pager.currentPage.coerceIn(0, carousel.slides.lastIndex)

    LaunchedEffect(carousel) {
        delay(400)
        onSave(carousel)
    }

    fun close() {
        onSave(carousel)
        onBack()
    }
    BackHandler { close() }

    fun update(change: (Carousel) -> Carousel) {
        carousel = change(carousel)
        exported = null
    }

    fun editSlides(goTo: Int, change: (MutableList<Slide>) -> Unit) {
        update { c -> c.copy(slides = c.slides.toMutableList().also(change)) }
        structure++
        scope.launch { pager.animateScrollToPage(goTo.coerceIn(0, carousel.slides.lastIndex)) }
    }

    suspend fun export(): List<Uri>? {
        busy = true
        val result = runCatching { Exporter.saveAll(context, renderer, carousel) }
        busy = false
        return result.fold(
            onSuccess = { exported = it; it },
            onFailure = { snackbar.showSnackbar("Couldn't save: ${it.message}"); null },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(carousel.title, maxLines = 1, overflow = TextOverflow.Ellipsis, color = Green) },
                navigationIcon = {
                    IconButton(onClick = { close() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(
                        enabled = !busy,
                        onClick = {
                            scope.launch {
                                val uris = exported ?: export() ?: return@launch
                                if (carousel.caption.isNotBlank()) {
                                    Exporter.copy(context, "Caption", carousel.caption)
                                }
                                Exporter.share(context, uris)
                            }
                        },
                    ) { Icon(Icons.Filled.Share, contentDescription = "Share") }
                    TextButton(
                        enabled = !busy,
                        onClick = {
                            scope.launch {
                                export()?.let {
                                    snackbar.showSnackbar("Saved ${it.size} slides to ${Exporter.folder(carousel)}")
                                }
                            }
                        },
                    ) { Text("Save") }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Cream),
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = Cream,
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
                .imePadding()
                .verticalScroll(rememberScrollState()),
        ) {
            HorizontalPager(
                state = pager,
                contentPadding = PaddingValues(horizontal = 48.dp),
                pageSpacing = 12.dp,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) { page ->
                SlidePreview(
                    carousel = carousel,
                    index = page,
                    renderer = renderer,
                    modifier = Modifier
                        .fillMaxWidth()
                        .shadow(2.dp, MaterialTheme.shapes.small),
                )
            }
            if (busy) {
                LinearProgressIndicator(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    color = Green,
                )
            }

            SlideToolbar(
                index = current,
                count = carousel.slides.size,
                onMoveLeft = { editSlides(current - 1) { it.add(current - 1, it.removeAt(current)) } },
                onMoveRight = { editSlides(current + 1) { it.add(current + 1, it.removeAt(current)) } },
                onDelete = { editSlides(current - 1) { it.removeAt(current) } },
                onAdd = { slide -> editSlides(current + 1) { it.add(current + 1, slide) } },
            )

            key(structure, current) {
                SlideFields(
                    slide = carousel.slides[current],
                    onChange = { s -> update { c -> c.copy(slides = c.slides.toMutableList().also { it[current] = s }) } },
                )
            }

            HorizontalDivider(Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
            CarouselSettings(carousel = carousel, onChange = { c -> update { c } }, onCopyCaption = {
                Exporter.copy(context, "Caption", carousel.caption)
                scope.launch { snackbar.showSnackbar("Caption copied") }
            })
            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun SlideToolbar(
    index: Int,
    count: Int,
    onMoveLeft: () -> Unit,
    onMoveRight: () -> Unit,
    onDelete: () -> Unit,
    onAdd: (Slide) -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "Slide ${index + 1} of $count",
            style = MaterialTheme.typography.titleSmall,
            color = Green,
            modifier = Modifier
                .padding(start = 8.dp)
                .weight(1f),
        )
        IconButton(onClick = onMoveLeft, enabled = index > 0) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Move slide left")
        }
        IconButton(onClick = onMoveRight, enabled = index < count - 1) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Move slide right")
        }
        IconButton(onClick = onDelete, enabled = count > 1) {
            Icon(Icons.Filled.Delete, contentDescription = "Delete slide")
        }
        Box {
            IconButton(onClick = { menu = true }) { Icon(Icons.Filled.Add, contentDescription = "Add slide") }
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                Templates.slideTypes.forEach { (name, slide) ->
                    DropdownMenuItem(text = { Text(name) }, onClick = { menu = false; onAdd(slide) })
                }
            }
        }
    }
}

@Composable
private fun SlideFields(slide: Slide, onChange: (Slide) -> Unit) {
    // Fields stay visible once shown, even if emptied while typing.
    var visible by remember { mutableStateOf(Field.entries.filter { slide.get(it).isNotBlank() }.toSet()) }
    var addMenu by remember { mutableStateOf(false) }

    Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Text position", style = MaterialTheme.typography.labelLarge, color = Gray)
            listOf("upper" to "Upper", "mid" to "Middle", "low" to "Lower").forEach { (pos, name) ->
                FilterChip(selected = slide.pos == pos, onClick = { onChange(slide.copy(pos = pos)) }, label = { Text(name) })
            }
        }

        Field.entries.filter { it in visible }.forEach { f ->
            key(f) {
                FieldEditor(
                    field = f,
                    initial = slide.get(f),
                    onValue = { onChange(slide.set(f, it)) },
                    onRemove = {
                        visible = visible - f
                        onChange(slide.set(f, ""))
                    },
                )
            }
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = slide.divider, onCheckedChange = { onChange(slide.copy(divider = it)) })
            Text("Thin line under headline", style = MaterialTheme.typography.bodyMedium)
        }

        val remaining = Field.entries.filter { it !in visible }
        if (remaining.isNotEmpty()) {
            Box {
                OutlinedButton(onClick = { addMenu = true }) {
                    Icon(Icons.Filled.Add, contentDescription = null)
                    Text("Add text field", Modifier.padding(start = 6.dp))
                }
                DropdownMenu(expanded = addMenu, onDismissRequest = { addMenu = false }) {
                    remaining.forEach { f ->
                        DropdownMenuItem(text = { Text(f.label) }, onClick = { addMenu = false; visible = visible + f })
                    }
                }
            }
        }
    }
}

@Composable
private fun FieldEditor(field: Field, initial: String, onValue: (String) -> Unit, onRemove: () -> Unit) {
    // Local text keeps exactly what was typed (e.g. a trailing new line) while the slide stores the cleaned value.
    var text by remember { mutableStateOf(initial) }
    OutlinedTextField(
        value = text,
        onValueChange = {
            text = it
            onValue(it)
        },
        label = { Text(field.label) },
        supportingText = if (field.hint.isNotEmpty()) {
            { Text(field.hint) }
        } else {
            null
        },
        trailingIcon = {
            IconButton(onClick = onRemove) { Icon(Icons.Filled.Close, contentDescription = "Remove ${field.label}") }
        },
        singleLine = !field.multiline,
        minLines = if (field.multiline) 2 else 1,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun CarouselSettings(carousel: Carousel, onChange: (Carousel) -> Unit, onCopyCaption: () -> Unit) {
    var label by remember { mutableStateOf(carousel.label) }
    var caption by remember { mutableStateOf(carousel.caption) }
    Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Carousel", style = MaterialTheme.typography.titleMedium, color = Green)
        OutlinedTextField(
            value = label,
            onValueChange = { label = it; onChange(carousel.copy(label = it)) },
            label = { Text("Top label on every slide") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = caption,
            onValueChange = { caption = it; onChange(carousel.copy(caption = it)) },
            label = { Text("Instagram caption") },
            supportingText = { Text("Copied automatically when you tap Share") },
            minLines = 4,
            modifier = Modifier.fillMaxWidth(),
        )
        Button(
            onClick = onCopyCaption,
            enabled = caption.isNotBlank(),
            colors = ButtonDefaults.buttonColors(containerColor = Green),
        ) { Text("Copy caption") }
    }
}
