import 'package:flutter/material.dart';
import 'package:cambric_design/cambric_design.dart';

class SlidesScreen extends StatefulWidget {
  const SlidesScreen({super.key});

  @override
  State<SlidesScreen> createState() => _SlidesScreenState();
}

class _SlidesScreenState extends State<SlidesScreen> {
  final List<String> _slides = ['Slide 1'];
  int _current = 0;
  final TextEditingController _controller = TextEditingController(text: 'Slide 1');
  bool _presenting = false;

  void _addSlide() {
    setState(() {
      _slides.add('Slide ${_slides.length + 1}');
      _current = _slides.length - 1;
      _controller.text = _slides[_current];
    });
  }

  void _deleteSlide() {
    if (_slides.length <= 1) return;
    setState(() {
      _slides.removeAt(_current);
      if (_current >= _slides.length) _current = _slides.length - 1;
      _controller.text = _slides[_current];
    });
  }

  void _togglePresent() {
    setState(() => _presenting = !_presenting);
  }

  @override
  Widget build(BuildContext context) {
    if (_presenting) {
      return Scaffold(
        body: Center(
          child: Text(_slides[_current], style: const TextStyle(fontSize: 48)),
        ),
        floatingActionButton: FloatingActionButton(
          onPressed: _togglePresent,
          child: const Icon(Icons.close),
        ),
      );
    }
    return DsPage(
      title: 'Slides',
      child: Row(
        children: [
          SizedBox(
            width: 160,
            child: Column(
              children: [
                Expanded(
                  child: ListView.builder(
                    itemCount: _slides.length,
                    itemBuilder: (context, i) => ListTile(
                      title: Text(_slides[i]),
                      selected: i == _current,
                      onTap: () {
                        setState(() {
                          _current = i;
                          _controller.text = _slides[i];
                        });
                      },
                    ),
                  ),
                ),
                Row(
                  children: [
                    IconButton(icon: const Icon(Icons.add), onPressed: _addSlide),
                    IconButton(icon: const Icon(Icons.delete), onPressed: _deleteSlide),
                    IconButton(icon: const Icon(Icons.play_arrow), onPressed: _togglePresent),
                  ],
                ),
              ],
            ),
          ),
          const VerticalDivider(),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                controller: _controller,
                maxLines: null,
                expands: true,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Slide content',
                ),
                onChanged: (v) => _slides[_current] = v.split('\n').first,
              ),
            ),
          ),
        ],
      ),
    );
  }
}