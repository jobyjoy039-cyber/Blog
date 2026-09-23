package com.ritvayalife.carousel

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import com.ritvayalife.carousel.ui.EditorScreen
import com.ritvayalife.carousel.ui.ListScreen
import com.ritvayalife.carousel.ui.RitvayaTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repo = CarouselRepository(applicationContext).also { it.seedIfNeeded() }
        val renderer = SlideRenderer(applicationContext)
        setContent {
            RitvayaTheme {
                App(repo, renderer)
            }
        }
    }
}

@Composable
private fun App(repo: CarouselRepository, renderer: SlideRenderer) {
    var openSlug by rememberSaveable { mutableStateOf<String?>(null) }
    var carousels by remember { mutableStateOf(repo.loadAll()) }
    val slug = openSlug

    if (slug == null) {
        ListScreen(
            carousels = carousels,
            renderer = renderer,
            onOpen = { openSlug = it },
            onCreate = { topic -> openSlug = repo.create(topic).slug },
            onDuplicate = { c -> repo.duplicate(c); carousels = repo.loadAll() },
            onDelete = { c -> repo.delete(c.slug); carousels = repo.loadAll() },
        )
    } else {
        val initial = remember(slug) { repo.load(slug) }
        if (initial == null) {
            LaunchedEffect(slug) { openSlug = null }
        } else {
            EditorScreen(
                initial = initial,
                renderer = renderer,
                onSave = repo::save,
                onBack = {
                    carousels = repo.loadAll()
                    openSlug = null
                },
            )
        }
    }
}
