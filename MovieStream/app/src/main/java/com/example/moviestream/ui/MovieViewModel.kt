package com.example.moviestream.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.moviestream.data.CatalogRepository
import com.example.moviestream.data.Movie
import com.example.moviestream.data.UserLibrary
import com.example.moviestream.data.WatchProgress
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class HomeRow(val title: String, val movies: List<Movie>)

sealed interface CatalogState {
    data object Loading : CatalogState
    data class Error(val message: String) : CatalogState
    data class Ready(val movies: List<Movie>) : CatalogState
}

class MovieViewModel(app: Application) : AndroidViewModel(app) {

    private val repository = CatalogRepository(app)
    val library = UserLibrary.get(app)

    private val _catalog = MutableStateFlow<CatalogState>(CatalogState.Loading)
    val catalog: StateFlow<CatalogState> = _catalog.asStateFlow()

    private val movies = MutableStateFlow<List<Movie>>(emptyList())

    val progress: StateFlow<Map<String, WatchProgress>> = library.progress
    val myListIds: StateFlow<Set<String>> = library.myList

    val featured: StateFlow<Movie?> = movies.map { list ->
        list.firstOrNull { it.featured } ?: list.firstOrNull()
    }.stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val rows: StateFlow<List<HomeRow>> = combine(movies, library.progress) { list, progress ->
        buildList {
            val continueWatching = list.filter { progress[it.id]?.isResumable == true }
            if (continueWatching.isNotEmpty()) add(HomeRow("Continue watching", continueWatching))
            add(HomeRow("Trending now", list.filter { it.featured }.ifEmpty { list }))
            list.flatMap { it.genres }.distinct().forEach { genre ->
                add(HomeRow(genre, list.filter { genre in it.genres }))
            }
        }
    }.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    val myList: StateFlow<List<Movie>> = combine(movies, library.myList) { list, ids ->
        list.filter { it.id in ids }
    }.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    init {
        reload()
    }

    fun reload() {
        _catalog.value = CatalogState.Loading
        viewModelScope.launch {
            runCatching { repository.load() }
                .onSuccess {
                    movies.value = it
                    _catalog.value = CatalogState.Ready(it)
                }
                .onFailure { _catalog.value = CatalogState.Error(it.message ?: "Couldn't load movies") }
        }
    }

    fun movie(id: String): Movie? = movies.value.firstOrNull { it.id == id }

    fun search(query: String): List<Movie> {
        val q = query.trim()
        if (q.isEmpty()) return movies.value
        return movies.value.filter { movie ->
            movie.title.contains(q, ignoreCase = true) ||
                movie.genres.any { it.contains(q, ignoreCase = true) } ||
                movie.description.contains(q, ignoreCase = true)
        }
    }

    fun toggleMyList(id: String) = library.toggleMyList(id)
}
