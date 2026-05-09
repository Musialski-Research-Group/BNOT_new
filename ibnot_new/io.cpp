#include "scene.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <iostream>

#include "console_color.h"

namespace {

std::string lowercase(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(),
                   [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return value;
}

bool has_suffix_case_insensitive(const std::string& value, const std::string& suffix)
{
    std::string lower_value = lowercase(value);
    std::string lower_suffix = lowercase(suffix);
    if (lower_value.size() < lower_suffix.size()) return false;
    return lower_value.compare(lower_value.size() - lower_suffix.size(),
                               lower_suffix.size(),
                               lower_suffix) == 0;
}

} // namespace

void Scene::load_image(const std::string& filename)
{
    bool ok = m_domain.load(filename);
    if (!ok) return;
    
    m_rt.set_boundary(m_domain.get_dx(),
                      m_domain.get_dy());
    std::cout << "Dx vs Dy: " << m_domain.get_dx() << " ; " << m_domain.get_dy() << std::endl;
}

void Scene::load_points(const std::string& filename)
{
    if (!m_domain.is_valid()) return;
    
    std::vector<FT> weights;
    std::vector<Point> points;
    if (has_suffix_case_insensitive(filename, ".dat"))
    {
        load_dat(filename, points);
        weights.resize(points.size(), 0.0);
    }
    
    if (!points.empty())
    {
        clear();
        init_colors(points.size());
        construct_triangulation(points, weights);
        return;
    }
    
    std::cout << red << "try (.dat) file format" << white << std::endl;
    return;
}

void Scene::load_dat(const std::string& filename, std::vector<Point>& points) const
{
    std::ifstream ifs(filename.c_str());
    Point point;
    while (ifs >> point) points.push_back(point);
    ifs.close();
}

void Scene::save_points(const std::string& filename) const
{
    std::vector<Point> points;
    collect_visible_points(points);
    
    if (has_suffix_case_insensitive(filename, ".dat"))
    {
        save_dat(filename, points);
        return;
    }
    
    if (has_suffix_case_insensitive(filename, ".txt"))
    {
        save_txt(filename, points);
        return;
    }
    
    if (has_suffix_case_insensitive(filename, ".eps"))
    {
        save_eps(filename);
        return;
    }

    std::cout << red << "try (.dat, .txt, .eps) file format" << white << std::endl;
}

void Scene::save_dat(const std::string& filename, const std::vector<Point>& points) const
{
    std::ofstream ofs(filename.c_str());
    ofs.precision(20);

    for (unsigned i = 0; i < points.size(); ++i)
    {
        ofs << points[i] << std::endl;
    }
    ofs.close();
}

void Scene::save_txt(const std::string& filename, const std::vector<Point>& points) const
{
    std::ofstream ofs(filename.c_str());
    ofs.precision(20);

    ofs << points.size() << std::endl;
    for (unsigned i = 0; i < points.size(); ++i)
    {
        ofs << points[i] << std::endl;
    }
    ofs.close();
}

void Scene::save_eps(const std::string& filename) const
{
    double dx = m_domain.get_dx();
    double dy = m_domain.get_dy();

    double scale = 512.0;
    double radius = 0.002;

    double wx = dx * scale;
    double wy = dy * scale;

    double min_x = 0;
    double max_x = 2.0 * wx;
    double min_y = 0;
    double max_y = 2.0 * wy;

    std::ofstream ofs(filename.c_str());
    ofs.precision(20);

    ofs << "%!PS-Adobe-3.1 EPSF-3.0\n";
    ofs << "%%HiResBoundingBox: " 
    << min_x << " " << min_y << " " << max_x << " " << max_y << std::endl;
    ofs << "%%BoundingBox: " 
    << min_x << " " << min_y << " " << max_x << " " << max_y << std::endl;
    ofs << "%%CropBox: " 
    << min_x << " " << min_y << " " << max_x << " " << max_y << "\n";
    
    ofs << "/radius { " << radius << " } def\n";
    ofs << "/p { radius 0 360 arc closepath fill stroke } def\n";
    ofs << "gsave " << scale << " " << scale << " scale\n";
    ofs << "0 0 0 setrgbcolor" << std::endl;

    for (unsigned i = 0; i < m_vertices.size(); ++i) 
    {
        Vertex_handle vi = m_vertices[i];
        if (vi->is_hidden()) continue;

        const Point& pi = vi->get_position();
        ofs << pi.x() + dx << " " << pi.y() + dy << " p" << std::endl;
    }
    ofs << "grestore" << std::endl;
    ofs.close();
}
