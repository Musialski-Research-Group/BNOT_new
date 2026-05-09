#include "scene.h"
#include "timer.h"

FT Scene::compute_weight_threshold(FT epsilon) const
{
    // reference: 1e-4 for 1000 sites
    FT A = compute_value_integral();
    unsigned N = count_visible_sites();
    return  (0.1*epsilon) * (A) / FT(N);
}

FT Scene::compute_position_threshold(FT epsilon) const
{
    // reference: 1e-4 for 1000 sites
    FT A = compute_value_integral();
    unsigned N = count_visible_sites();
    return (0.1*epsilon) * (std::sqrt(A*A*A)) / FT(N);
}

FT Scene::compute_wcvt_energy()
{
    if (m_timer_on) Timer::start_timer(m_timer, COLOR_BLUE, "Energy");

    FT cvt = 0.0;
    FT w_dot_V = 0.0;
    for (unsigned i = 0; i < m_vertices.size(); ++i)
    {    
        Vertex_handle vi = m_vertices[i];
        if (vi->is_hidden()) continue;
        
        FT Vi = vi->compute_area();
        FT wi = vi->get_weight();
        FT Ci = m_capacities[i];
        w_dot_V += wi * (Vi - Ci);        
        cvt += vi->compute_variance();
    }
    
    if (m_timer_on) Timer::stop_timer(m_timer, COLOR_BLUE);

    return (w_dot_V - cvt);
}

void Scene::compute_weight_gradient(std::vector<FT>& gradient, FT coef)
{
    if (m_timer_on) Timer::start_timer(m_timer, COLOR_BLUE, "WGrad");
    
    gradient.clear();
    for (unsigned i = 0; i < m_vertices.size(); ++i)
    {
        Vertex_handle vi = m_vertices[i];
        if (vi->is_hidden()) continue;
        
        FT Ci = m_capacities[i];
        FT Vi = vi->compute_area();
        FT Gi = Vi - Ci;
        gradient.push_back(coef * Gi);
    }
    
    if (m_timer_on) Timer::stop_timer(m_timer, COLOR_BLUE);
}

void Scene::compute_position_gradient(std::vector<Vector>& gradient, FT coef)
{
    if (m_timer_on) Timer::start_timer(m_timer, COLOR_BLUE, "XGrad");

    gradient.clear();
    for (unsigned i = 0; i < m_vertices.size(); ++i)
    {
        Vertex_handle vi = m_vertices[i];        
        if (vi->is_hidden()) continue;
 
        FT Vi = vi->compute_area();
        Point xi = vi->get_position();
        Point ci = vi->compute_centroid();
        Vector gi = -2.0*Vi*(xi - ci);
        gradient.push_back(coef * gi);
    }
    
    if (m_timer_on) Timer::stop_timer(m_timer, COLOR_BLUE);
}

void Scene::compute_capacity_error_stats(FT& mean_abs,
                                         FT& max_abs,
                                         FT& rms_abs) const
{
    mean_abs = 0.0;
    max_abs = 0.0;
    rms_abs = 0.0;

    unsigned visible = 0;
    for (unsigned i = 0; i < m_vertices.size(); ++i)
    {
        Vertex_handle vi = m_vertices[i];
        if (vi->is_hidden()) continue;

        FT error = std::abs(vi->compute_area() - m_capacities[i]);
        mean_abs += error;
        max_abs = std::max(max_abs, error);
        rms_abs += error * error;
        visible++;
    }

    if (visible == 0) return;

    mean_abs /= FT(visible);
    rms_abs = std::sqrt(rms_abs / FT(visible));
}
