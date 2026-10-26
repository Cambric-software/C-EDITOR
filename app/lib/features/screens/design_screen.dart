import 'package:flutter/material.dart';
import 'package:cambric_design/cambric_design.dart';

class DesignScreen extends StatefulWidget {
  const DesignScreen({super.key});

  @override
  State<DesignScreen> createState() => _DesignScreenState();
}

class _DesignScreenState extends State<DesignScreen> {
  final List<_DesignItem> _items = [];
  Color _selectedColor = Colors.blue;
  int? _selectedIndex;

  void _addBox() {
    setState(() {
      _items.add(_DesignItem(
        offset: const Offset(100, 100),
        color: _selectedColor,
        text: 'Box',
      ));
    });
  }

  void _addText() {
    setState(() {
      _items.add(_DesignItem(
        offset: const Offset(150, 150),
        color: _selectedColor,
        text: 'Text',
        isText: true,
      ));
    });
  }

  void _deleteSelected() {
    if (_selectedIndex != null) {
      setState(() {
        _items.removeAt(_selectedIndex!);
        _selectedIndex = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return DsPage(
      title: 'Design',
      child: Row(
        children: [
          // Layers panel
          SizedBox(
            width: 160,
            child: Column(
              children: [
                const Text('Layers'),
                Expanded(
                  child: ListView.builder(
                    itemCount: _items.length,
                    itemBuilder: (context, i) => ListTile(
                      title: Text(_items[i].text),
                      selected: i == _selectedIndex,
                      onTap: () => setState(() => _selectedIndex = i),
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: _deleteSelected,
                ),
              ],
            ),
          ),
          const VerticalDivider(),
          // Canvas
          Expanded(
            child: Stack(
              children: [
                for (int i = 0; i < _items.length; i++)
                  Positioned(
                    left: _items[i].offset.dx,
                    top: _items[i].offset.dy,
                    child: GestureDetector(
                      onPanUpdate: (details) {
                        setState(() {
                          _items[i].offset += details.delta;
                        });
                      },
                      onTap: () => setState(() => _selectedIndex = i),
                      child: Container(
                        width: _items[i].isText ? null : 80,
                        height: _items[i].isText ? null : 80,
                        color: _items[i].isText ? null : _items[i].color,
                        child: Center(
                          child: Text(
                            _items[i].text,
                            style: TextStyle(color: _items[i].color),
                          ),
                        ),
                      ),
                    ),
                  ),
                Positioned(
                  bottom: 16,
                  right: 16,
                  child: Column(
                    children: [
                      DropdownButton<Color>(
                        value: _selectedColor,
                        items: const [
                          DropdownMenuItem(value: Colors.blue, child: Text('Blue')),
                          DropdownMenuItem(value: Colors.red, child: Text('Red')),
                          DropdownMenuItem(value: Colors.green, child: Text('Green')),
                          DropdownMenuItem(value: Colors.black, child: Text('Black')),
                        ],
                        onChanged: (c) {
                          if (c != null) setState(() => _selectedColor = c);
                        },
                      ),
                      FloatingActionButton(
                        heroTag: 'box',
                        onPressed: _addBox,
                        child: const Icon(Icons.crop_square),
                      ),
                      const SizedBox(height: 8),
                      FloatingActionButton(
                        heroTag: 'text',
                        onPressed: _addText,
                        child: const Icon(Icons.text_fields),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DesignItem {
  _DesignItem({
    required this.offset,
    required this.color,
    required this.text,
    this.isText = false,
  });

  Offset offset;
  Color color;
  String text;
  bool isText;
}